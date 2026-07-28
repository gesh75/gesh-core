# gesh-core

Shared core package for the GESH Financial engine and its product repos. Phase 3 de-duplication target: logic here is consumed by Gesh-Project and gesh-project-trading, so changes ripple.

**Stack.** Python >=3.12, packaged via `pyproject.toml`. ruff + pytest.

**Layout.** `src/` package source, `tests/`, `docs/`

## Build and test

```bash
python -m pip install --upgrade pip
pip install -e '.[dev]' || pip install -e .
python -m pytest -q
```

Run the tests before proposing a change is done. If you cannot run them, say so explicitly
rather than claiming the change is verified.

## Engineering conventions (non-negotiable)

- **Type hints on every function signature.** No bare `def f(x):`.
- **async/await for all I/O.** Never block the event loop with sync network or disk calls.
- **Immutable data.** Return new objects; do not mutate arguments in place.
- **Tests first.** Write the failing test, watch it fail, then implement. Target 80%+ coverage.
- **Small files.** 200-400 lines typical, 800 hard max. Extract modules rather than growing a file.
- **Small functions.** Under 50 lines. Nesting no deeper than 4 levels - use early returns.
- **Handle every error explicitly.** Never swallow an exception silently. Log context server-side,
  return a friendly message user-side.
- **Validate at boundaries.** Never trust user input, API responses, or file contents.
- **No hardcoded secrets, ever.** Environment variables or a secret manager only. No credentials
  in code, comments, logs, tests, or fixtures.
- **Conventional Commits**: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`, `perf:`, `ci:`.
  Imperative mood, lower case, no trailing period. Do **not** add `Co-authored-by` trailers.

## Before you propose a change

1. Read the surrounding code and match its idiom, naming, and comment density.
2. Prefer a battle-tested library over hand-rolled utility code.
3. If you touch auth, user input, DB queries, file paths, or external calls, re-read the
   security rules above before finishing.

## This is a shared library - treat the public API as a contract

- Downstream consumers are `Gesh-Project` and `gesh-project-trading`. A breaking change here
  breaks both. Prefer additive changes; deprecate before removing.
- Anything exported from `src/` top-level is public API. Renaming or changing a signature
  requires a note in the PR description naming the affected downstream call sites.
- Risk-band and sizing logic is canonical here. Do not fork or re-implement it downstream -
  if a consumer needs different behaviour, parameterise it here instead.
- Keep this package dependency-light. New third-party dependencies need justification in the PR.

## Pull requests

- Title in Conventional Commits form.
- Body covers: what changed, why, blast radius, and a test plan as a checklist.
- Summarise the whole commit range, not just the last commit.
