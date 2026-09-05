"""
Kelly Criterion Position Sizer
Calculates optimal position sizes using:
  - Full Kelly: f* = (μ - r) / σ²  (continuous, log-normal approximation)
  - Half-Kelly: f*/2               (practical, reduces ruin risk)
  - Win-rate Kelly: f* = W - (1-W)/R  (discrete, trade history based)
  - Volatility-adjusted cap: never exceed 25% per position
Inputs per holding: price history (90d), analyst upside, current allocation
"""

import logging
import math
import os
import sys

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

HALF_KELLY_FACTOR = 0.5   # conservative multiplier
_DEFAULT_MAX_POSITION_PCT = 0.25


def _parse_position_cap(value: str | None, fallback: float) -> float:
    """Return a finite position cap in the inclusive range [0, 1]."""
    if value is None:
        return fallback
    try:
        cap = float(value)
    except (TypeError, ValueError):
        return fallback
    return cap if math.isfinite(cap) and 0.0 <= cap <= 1.0 else fallback


# Per-position hard cap. Env-overridable (KELLY_MAX_POSITION_PCT) but the default
# stays 0.25 so the standalone kelly_size_holding path — consumed directly by
# consensus.py / run_engines2.py and the /kelly dashboard — is unchanged.
MAX_POSITION_PCT = _parse_position_cap(
    os.getenv("KELLY_MAX_POSITION_PCT"), _DEFAULT_MAX_POSITION_PCT
)
MIN_HISTORY_DAYS  = 30    # minimum trading days needed

# ─── H2: portfolio-level reconciliation knobs (read at CALL time) ──────────────
# Summing independent per-name Kellys systematically OVERBETS once positions are
# correlated (EXA's #1 Kelly mistake). run_kelly_analysis reconciles the book with
# two overlays, both env-tunable without touching the per-name math:
#   • a correlation haircut — a name inside an N-name correlated cluster is sized
#     1/sqrt(N) (the standard diversification adjustment), so 3 AI-semis names are
#     not budgeted as 3 independent edges;
#   • a gross-exposure cap — if the haircut book still sums above the cap, every
#     position is scaled down proportionally so total Kelly never exceeds it.
_DEFAULT_MAX_GROSS_PCT = 1.0    # 100% of portfolio (gross long)
_DEFAULT_CORR_THRESHOLD = 0.70  # |corr| at/above which two names share a cluster


def _max_position_pct() -> float:
    """Per-position hard cap, read at CALL time (env KELLY_MAX_POSITION_PCT).

    The module constant above keeps its import-time value for existing importers
    (consensus.py / run_engines2.py read it as a constant), but sizing itself
    honors env changes in long-lived processes (server/autopilot) like every
    other knob in this module.
    """
    return _parse_position_cap(os.getenv("KELLY_MAX_POSITION_PCT"), MAX_POSITION_PCT)


def _max_gross_exposure() -> float:
    """Gross-exposure cap as a fraction (1.0 = 100%). Env KELLY_MAX_GROSS_PCT."""
    return _parse_position_cap(os.getenv("KELLY_MAX_GROSS_PCT"), _DEFAULT_MAX_GROSS_PCT)


def _corr_threshold() -> float:
    """Correlation clustering threshold. Env KELLY_CORR_THRESHOLD."""
    try:
        return float(os.getenv("KELLY_CORR_THRESHOLD", str(_DEFAULT_CORR_THRESHOLD)))
    except (TypeError, ValueError):
        return _DEFAULT_CORR_THRESHOLD


# ─── M1: transaction-cost haircut ─────────────────────────────────────────────
# Kelly assumes frictionless markets; thin edges should shrink (or vanish) once
# costs are netted out (EXA: use mu_net = mu - costs). Round-trip cost in bps is
# amortized over a rebalance horizon into a per-DAY drag subtracted from mu in
# the continuous estimator. Default 10bps over 21 trading days ≈ 0.5bps/day — it
# barely touches a strong edge but pulls a marginal one toward zero.
_DEFAULT_COST_BPS = 10.0          # round-trip transaction cost (bps)
_DEFAULT_REBALANCE_DAYS = 21.0    # amortization horizon (≈ 1 trading month)


def _cost_drag_daily() -> float:
    """Per-day return drag from transaction costs. Env KELLY_COST_BPS / KELLY_REBALANCE_DAYS."""
    try:
        bps = float(os.getenv("KELLY_COST_BPS", str(_DEFAULT_COST_BPS)))
        days = float(os.getenv("KELLY_REBALANCE_DAYS", str(_DEFAULT_REBALANCE_DAYS)))
    except (TypeError, ValueError):
        bps, days = _DEFAULT_COST_BPS, _DEFAULT_REBALANCE_DAYS
    if days <= 0:
        return 0.0
    return (bps / 10_000.0) / days


# ─── M2: serial-dependence (autocorrelation) shrinkage ────────────────────────
# Standard Kelly assumes independent bets, but daily returns are serially
# correlated, which inflates the variance of cumulative returns and overstates
# the reliability of mu (EXA: adjust the effective sample size). We shrink the
# sized fraction by sqrt(N_eff / N) = sqrt((1-rho)/(1+rho)) using the lag-1
# autocorrelation rho (only when rho > 0; clamped to a floor so an extreme rho
# can't zero the position). Toggle off with KELLY_AUTOCORR_SHRINK=0.
_AUTOCORR_SHRINK_FLOOR = 0.30


def _autocorr_shrink(returns: np.ndarray) -> tuple[float, float]:
    """Return (lag1_autocorr, shrink_factor∈[floor,1]). Factor 1.0 when disabled,
    flat, or non-positively autocorrelated (never UP-sizes)."""
    if os.getenv("KELLY_AUTOCORR_SHRINK", "1") in ("0", "false", "False"):
        return 0.0, 1.0
    if returns is None or len(returns) < 3:
        return 0.0, 1.0
    a, b = returns[:-1], returns[1:]
    if float(np.std(a)) == 0.0 or float(np.std(b)) == 0.0:
        return 0.0, 1.0
    with np.errstate(invalid="ignore", divide="ignore"):
        rho = float(np.corrcoef(a, b)[0, 1])
    if not np.isfinite(rho) or rho <= 0.0:
        return (rho if np.isfinite(rho) else 0.0), 1.0
    factor = float(np.sqrt((1.0 - rho) / (1.0 + rho)))
    return rho, max(_AUTOCORR_SHRINK_FLOOR, min(1.0, factor))

def _fetch_returns(symbol: str, days: int = 90) -> pd.Series | None:
    """Daily returns as a DATE-indexed Series (index normalized to naive dates).

    The index is what lets ``_correlation_haircuts`` align symbols by calendar
    date instead of by array position — positional alignment misdated every
    series with a gap (halt day, listing gap, partial fetch) and produced wrong
    cluster sizes. The sizing math itself is date-agnostic: ``kelly_size_holding``
    coerces to ndarray, and test seams may inject plain ndarrays (the haircut
    pass then falls back to positional alignment).
    """
    try:
        # Standard period string ("2y") avoids the "possibly delisted" errors that
        # custom Nd period strings caused on rebranded crypto tickers (MATIC, UNI1),
        # without downloading decades of history to use 90 days (period="max" was
        # ~50-100x the payload per symbol).
        try:
            raw = yf.Ticker(symbol).history(period="2y", auto_adjust=True)
        except Exception:
            raw = None
        if raw is None or raw.empty:
            # Yahoo 401/crumb storm — fall back to Robinhood OHLCV only when the
            # host already imported its trusted `price_source`. Discovering that
            # name via sys.path (cwd is first) would execute a planted module.
            ps = sys.modules.get("price_source")
            raw = (
                ps.rh_fallback(symbol, period="2y", interval="1d")
                if ps is not None
                else None
            )
        if raw is None or raw.empty:
            return None
        raw = raw.tail(days + 10)
        if len(raw) < MIN_HISTORY_DAYS:
            return None
        closes = raw["Close"]
        if hasattr(closes, "squeeze"):
            closes = closes.squeeze()
        returns = closes.pct_change().dropna().astype(float)
        # Normalize the index for cross-source alignment: Yahoo is tz-aware
        # (America/New_York), the Robinhood fallback may be naive — without
        # stripping tz + time-of-day, an inner join across sources matches
        # ZERO dates and the haircut silently fails open.
        idx = pd.DatetimeIndex(returns.index)
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        returns.index = idx.normalize()
        return returns[~returns.index.duplicated(keep="last")]
    except Exception as e:  # noqa: BLE001 — fetch is best-effort; None → caller skips
        logger.debug("_fetch_returns failed for %s: %s", symbol, e)
        return None

def _continuous_kelly(returns: np.ndarray, risk_free_daily: float = 0.0,
                      cost_drag: float = 0.0) -> dict:
    """Log-normal Kelly: f* = (μ − r − costs) / σ².

    `cost_drag` is a per-period transaction-cost haircut on μ (default 0.0 keeps
    the pure estimator frictionless); kelly_size_holding passes the configured
    drag so thin edges shrink toward zero once costs are netted out.
    """
    mu  = float(np.mean(returns))
    sig = float(np.std(returns))
    if sig == 0:
        return {"kelly_pct": 0.0, "method": "continuous"}
    excess = mu - risk_free_daily - cost_drag
    raw_kelly = excess / (sig ** 2)
    return {
        "kelly_pct": raw_kelly,
        "mu_daily":  round(mu * 100, 4),
        "sigma_daily": round(sig * 100, 4),
        "sharpe_annualized": round((mu / sig) * np.sqrt(252), 2) if sig > 0 else 0,
        "method": "continuous"
    }

def _discrete_kelly(returns: np.ndarray, threshold: float = 0.0) -> dict:
    """Discrete Kelly: f* = W - (1-W)/R using daily return wins/losses"""
    wins   = returns[returns > threshold]
    losses = returns[returns <= threshold]
    W = len(wins) / len(returns) if len(returns) > 0 else 0.5
    avg_win  = float(np.mean(np.abs(wins)))  if len(wins)   > 0 else 0.01
    avg_loss = float(np.mean(np.abs(losses))) if len(losses) > 0 else 0.01
    R = avg_win / avg_loss if avg_loss > 0 else 1.0
    raw_kelly = W - (1 - W) / R
    return {
        "kelly_pct":  raw_kelly,
        "win_rate":   round(W * 100, 1),
        "avg_win_pct": round(avg_win * 100, 3),
        "avg_loss_pct": round(avg_loss * 100, 3),
        "payoff_ratio": round(R, 2),
        "method": "discrete"
    }

def _volatility_score(returns: np.ndarray) -> str:
    ann_vol = float(np.std(returns)) * np.sqrt(252) * 100
    if ann_vol < 30:
        return "LOW"
    if ann_vol < 60:
        return "MEDIUM"
    if ann_vol < 100:
        return "HIGH"
    return "EXTREME"

def _max_drawdown(returns: np.ndarray) -> float:
    cumulative = np.cumprod(1 + returns)
    running_max = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - running_max) / running_max
    return float(np.min(drawdown)) * 100  # negative %

def kelly_size_holding(
    symbol: str,
    current_equity: float,
    total_portfolio: float,
    avg_cost: float,
    current_price: float,
    analyst_upside_pct: float | None = None,
    ai_eval: dict | None = None,
    returns: np.ndarray | None = None,
) -> dict:
    """Full Kelly analysis for one holding.

    `returns` may be injected directly (pre-fetched daily returns) — used by the
    product repo's unit tests to run network-free. When None, returns are fetched
    via `_fetch_returns` (Yahoo 2y + Robinhood fallback; rule #43-hardened against
    the "possibly delisted" errors that short Nd period strings caused on
    rebranded crypto tickers).
    """
    if returns is None:
        returns = _fetch_returns(symbol, days=90)
    if returns is not None:
        # Sizing math is date-agnostic — accept either the dated Series from
        # _fetch_returns or a plain injected ndarray, compute on ndarray.
        returns = np.asarray(returns, dtype=float)
    if returns is None or len(returns) < MIN_HISTORY_DAYS:
        return {
            "symbol": symbol,
            "error": "Insufficient price history",
            "recommended_pct": None,
            "recommended_usd": None,
        }

    cost_drag = _cost_drag_daily()                       # M1: net costs out of μ
    cont   = _continuous_kelly(returns, cost_drag=cost_drag)
    disc   = _discrete_kelly(returns)
    ann_vol = float(np.std(returns)) * np.sqrt(252) * 100
    mdd     = _max_drawdown(returns)

    # Blend: 60% continuous + 40% discrete (more stable)
    raw_blend = 0.6 * cont["kelly_pct"] + 0.4 * disc["kelly_pct"]

    # M2: serial-dependence shrinkage — daily returns are not independent bets.
    autocorr_lag1, autocorr_factor = _autocorr_shrink(returns)
    raw_blend *= autocorr_factor

    # Analyst upside boost: scale by upside confidence (cap +20% adjustment)
    if analyst_upside_pct is not None and analyst_upside_pct > 0:
        boost = min(analyst_upside_pct / 100.0 * 0.2, 0.2)
        raw_blend = raw_blend * (1 + boost)

    # Master Signal Valuation Penalty (from AI deep analysis)
    ai_penalty = 1.0
    if ai_eval:
        verdict = str(ai_eval.get("verdict", "")).upper()
        # "pct_diff" is negative if overvalued
        pct_diff = float(ai_eval.get("pct_diff", 0) or 0)
        
        if verdict == "AVOID" or verdict == "SELL":
            ai_penalty = 0.5  # Heavy penalty
        elif pct_diff < -15.0:
            ai_penalty = 0.6  # Severe overvaluation penalty
        elif pct_diff < -5.0 or verdict == "REDUCE":
            ai_penalty = 0.8  # Slight overvaluation penalty
            
        raw_blend = raw_blend * ai_penalty

    # Apply half-Kelly and hard cap
    half_kelly = raw_blend * HALF_KELLY_FACTOR
    final_pct  = max(0.0, min(half_kelly, _max_position_pct()))

    # Current vs optimal
    current_pct = current_equity / total_portfolio if total_portfolio > 0 else 0
    recommended_usd = final_pct * total_portfolio
    delta_usd = recommended_usd - current_equity
    delta_pct = (final_pct - current_pct) * 100

    # Signal
    if final_pct == 0:
        action = "AVOID"
        action_color = "red"
    elif current_pct > final_pct * 1.3:
        action = "TRIM"
        action_color = "yellow"
    elif current_pct < final_pct * 0.6:
        action = "ADD"
        action_color = "green"
    else:
        action = "HOLD"
        action_color = "cyan"

    # PnL
    pnl_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0

    return {
        "symbol":          symbol,
        "current_pct":     round(current_pct * 100, 1),
        "optimal_pct":     round(final_pct * 100, 1),
        "recommended_usd": round(recommended_usd, 2),
        "delta_usd":       round(delta_usd, 2),
        "delta_pct":       round(delta_pct, 1),
        "action":          action,
        "action_color":    action_color,
        "win_rate":        disc["win_rate"],
        "payoff_ratio":    disc["payoff_ratio"],
        "sharpe":          cont.get("sharpe_annualized", 0),
        "ann_volatility":  round(ann_vol, 1),
        "volatility_tier": _volatility_score(returns),
        "max_drawdown":    round(mdd, 1),
        "pnl_pct":         round(pnl_pct, 1),
        "raw_kelly":       round(raw_blend * 100, 1),
        "half_kelly":      round(final_pct * 100, 1),
        "analyst_upside":  analyst_upside_pct,
        "ai_penalty":      ai_penalty,
        "mu_daily":        cont.get("mu_daily", 0),
        "sigma_daily":     cont.get("sigma_daily", 0),
        "cost_drag_daily": round(cost_drag, 6),
        "autocorr_lag1":   round(autocorr_lag1, 3),
        "autocorr_shrink": round(autocorr_factor, 3),
    }

def _classify_action(current_pct: float, final_pct: float) -> tuple[str, str]:
    """(action, color) from current vs target weight — mirrors kelly_size_holding."""
    if final_pct == 0:
        return "AVOID", "red"
    if current_pct > final_pct * 1.3:
        return "TRIM", "yellow"
    if current_pct < final_pct * 0.6:
        return "ADD", "green"
    return "HOLD", "cyan"


def _correlation_haircuts(
    symbols: list[str],
    returns_by_symbol: dict[str, pd.Series | np.ndarray | None],
    threshold: float,
) -> dict[str, float]:
    """Map symbol → diversification haircut (≤ 1.0) based on return correlation.

    A name in an N-member correlated cluster (|corr| ≥ threshold with N-1 peers,
    itself included → N) is scaled by 1/sqrt(N). Names with no usable returns, or
    no correlated peer, get 1.0 (fail-open — the overlay never UP-sizes a name).

    Alignment: when every usable series is a date-indexed ``pd.Series`` (the
    production path via ``_fetch_returns``), each symbol pair is inner-joined
    on its shared calendar dates — a mid-series gap (halt day, listing gap,
    partial fetch) no longer shifts one symbol's Monday against another's
    Tuesday, and an unrelated sparse symbol cannot suppress valid peers.
    Plain ndarrays (test seams / pre-dated injections) keep the positional
    last-L-points fallback.
    """
    haircuts = {s: 1.0 for s in symbols}
    # Need ≥ 2 names with ≥ 2 aligned points to correlate. Materialize the
    # non-None series up front so the None branch is excluded once.
    series: dict[str, pd.Series | np.ndarray] = {
        s: r for s in symbols
        if (r := returns_by_symbol.get(s)) is not None and len(r) >= 2
    }
    usable = list(series)
    if len(usable) < 2:
        return haircuts
    if all(isinstance(series[s], pd.Series) for s in usable):
        # Date-align each pair independently. A global inner join would let one
        # disjoint/sparse name erase usable history for every other pair.
        corr = np.full((len(usable), len(usable)), np.nan, dtype=float)
        for i, left in enumerate(usable):
            corr[i, i] = 1.0
            for j in range(i + 1, len(usable)):
                right = usable[j]
                pair = pd.concat(
                    [series[left], series[right]], axis=1, join="inner"
                ).dropna()
                if len(pair) < 2:
                    continue  # this pair has no usable overlap; fail open
                with np.errstate(invalid="ignore", divide="ignore"):
                    value = np.corrcoef(pair.to_numpy(dtype=float).T)[0, 1]
                corr[i, j] = corr[j, i] = value
    else:
        # Positional fallback: shortest common length, last L points.
        min_len = min(len(series[s]) for s in usable)
        if min_len < 2:
            return haircuts
        matrix = np.vstack([np.asarray(series[s], dtype=float)[-min_len:] for s in usable])
        with np.errstate(invalid="ignore", divide="ignore"):
            corr = np.corrcoef(matrix)
    corr = np.atleast_2d(corr)
    for i, s in enumerate(usable):
        # Cluster size = self + peers at/above threshold (ignore NaNs from flat series).
        peers = sum(
            1 for j in range(len(usable))
            if j != i and np.isfinite(corr[i, j]) and abs(corr[i, j]) >= threshold
        )
        cluster_size = 1 + peers
        if cluster_size > 1:
            haircuts[s] = 1.0 / np.sqrt(cluster_size)
    return haircuts


def _rescale_result(
    r: dict, equity: float, total_portfolio: float,
    corr_haircut: float, gross_factor: float,
) -> dict:
    """Return a NEW result dict with size scaled by corr_haircut × gross_factor.

    Recomputes the dollar/delta/action fields so the post-reconciliation row is
    internally consistent. Immutable: the input dict is not mutated.
    """
    out = dict(r)
    factor = corr_haircut * gross_factor
    final_pct = round(r["optimal_pct"] * factor, 1)          # still a percentage
    current_pct = r.get("current_pct", 0.0)
    recommended_usd = final_pct / 100.0 * total_portfolio
    action, color = _classify_action(current_pct, final_pct)
    out.update({
        "optimal_pct":     final_pct,
        "half_kelly":      final_pct,
        "recommended_usd": round(recommended_usd, 2),
        "delta_usd":       round(recommended_usd - equity, 2),
        "delta_pct":       round(final_pct - current_pct, 1),
        "action":          action,
        "action_color":    color,
        "corr_haircut":    round(corr_haircut, 3),
    })
    return out


def run_kelly_analysis(holdings: list[dict], total_portfolio: float,
                       analyst_targets: dict | None = None,
                       ai_verdicts: dict | None = None) -> dict:
    """Run Kelly on all holdings, return ranked results + portfolio summary.

    Per-name Kellys are reconciled at the portfolio level (H2) so a book of
    correlated, individually-capped positions can no longer sum to an overbet:
      1. each name is fetched once and sized via ``kelly_size_holding``;
      2. a correlation haircut shrinks names inside correlated clusters;
      3. a gross-exposure cap proportionally scales the whole book if it still
         sums above ``KELLY_MAX_GROSS_PCT``.
    ``gross_scale_factor`` / ``rescaled`` and per-row ``corr_haircut`` are surfaced
    so the dashboard can explain any trim.
    """
    eq_by_symbol: dict[str, float] = {}
    returns_by_symbol: dict[str, pd.Series | np.ndarray | None] = {}
    results = []
    for h in holdings:
        sym   = h.get("symbol", "")
        eq    = float(h.get("equity", 0))
        cost  = float(h.get("average_buy_price", 0))
        price = float(h.get("current_price", 0))
        upside = None
        if analyst_targets and sym in analyst_targets:
            upside = analyst_targets[sym].get("upside_pct")

        eval_dict = None
        if ai_verdicts and sym in ai_verdicts:
            eval_dict = ai_verdicts[sym]

        # Fetch returns ONCE per symbol and retain them for the correlation pass
        # (instead of letting kelly_size_holding fetch-and-discard internally).
        rets = _fetch_returns(sym, days=90)
        r = kelly_size_holding(sym, eq, total_portfolio, cost, price, upside,
                               eval_dict, returns=rets)
        results.append(r)
        eq_by_symbol[sym] = eq
        returns_by_symbol[sym] = rets

    # ── Reconciliation overlays (only rows with a numeric optimal_pct) ──────────
    sized = [r for r in results if isinstance(r.get("optimal_pct"), (int, float))]
    haircuts = _correlation_haircuts(
        [r["symbol"] for r in sized], returns_by_symbol, _corr_threshold()
    )

    # Gross-exposure cap after the haircut, applied proportionally.
    haircut_gross = sum(r["optimal_pct"] * haircuts.get(r["symbol"], 1.0) for r in sized)
    cap_pct = _max_gross_exposure() * 100.0
    gross_factor = 1.0
    if haircut_gross > cap_pct and haircut_gross > 0:
        gross_factor = cap_pct / haircut_gross
    rescaled = gross_factor < 1.0

    reconciled = [
        _rescale_result(r, eq_by_symbol.get(r["symbol"], 0.0), total_portfolio,
                        haircuts.get(r["symbol"], 1.0), gross_factor)
        for r in sized
    ]
    # Carry through any error rows (no optimal_pct) unchanged, tagged for clarity.
    for r in results:
        if not isinstance(r.get("optimal_pct"), (int, float)):
            reconciled.append({**r, "corr_haircut": 1.0})

    # Portfolio-level stats (post-reconciliation)
    allocated_pct   = sum(r["optimal_pct"] for r in reconciled if r.get("optimal_pct"))
    over_positions  = [r for r in reconciled if r.get("action") == "TRIM"]
    under_positions = [r for r in reconciled if r.get("action") == "ADD"]
    avoid_positions = [r for r in reconciled if r.get("action") == "AVOID"]
    # NaN guard: np.mean([]) is NaN — an all-AVOID/all-error book must report 0.0,
    # not leak NaN into the JSON payload (strict parsers reject it).
    positive_kellys = [
        r["half_kelly"] for r in reconciled
        if isinstance(r.get("half_kelly"), (int, float)) and r["half_kelly"] > 0
    ]

    return {
        "holdings":        sorted(reconciled, key=lambda x: x.get("optimal_pct", 0) or 0, reverse=True),
        "total_optimal_allocated_pct": round(allocated_pct, 1),
        "cash_recommended_pct": round(max(0, 100 - allocated_pct), 1),
        "gross_scale_factor":  round(gross_factor, 4),
        "rescaled":            rescaled,
        "trim_list":  [r["symbol"] for r in over_positions],
        "add_list":   [r["symbol"] for r in under_positions],
        "avoid_list": [r["symbol"] for r in avoid_positions],
        "portfolio_kelly_score": round(float(np.mean(positive_kellys)), 1) if positive_kellys else 0.0,
    }
