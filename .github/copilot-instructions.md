# gesh-core

Shared core package for the GESH Financial engine and its product repos (Phase 3
de-duplication). Consumed by `Gesh-Project` and `gesh-project-trading`, so changes ripple.

**Stack.** Python >=3.12, packaged via `pyproject.toml`. ruff + pytest.

**Layout.** `src/` package source, `tests/`, `docs/`

## Build and test

```bash
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
python -m pytest -q
```

The `dev` extra is declared in `pyproject.toml` - install it explicitly and let it fail loudly
if it cannot resolve, rather than silently falling back to a bare install without dev tooling.

Run the tests before calling a change done. If you cannot run them, say so explicitly rather
than claiming the change is verified.

## Engineering conventions (non-negotiable)

- **Type hints on every function signature.** No bare `def f(x):`.
- **async/await for I/O** in async code paths. Never block an event loop with a sync call.
- **Immutable data.** Return new objects; do not mutate arguments in place.
- **Tests first.** Write the failing test, watch it fail, then implement. Target 80%+ coverage.
- **Small files.** 200-400 lines typical, 800 hard max. Extract modules rather than growing a file.
- **Small functions.** Under 50 lines. Nesting no deeper than 4 levels - use early returns.
- **Handle every error explicitly.** Never swallow an exception silently.
- **Validate at boundaries.** Never trust user input, API responses, or file contents.
- **No hardcoded secrets, ever.** Environment variables or a secret manager only. No credentials
  in code, comments, logs, tests, or fixtures.
- **Conventional Commits**: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`, `perf:`, `ci:`.
  Imperative mood, lower case, no trailing period. Do **not** add `Co-authored-by` trailers.

## This is a shared library - the public API is a contract

- Downstream consumers are `Gesh-Project` and `gesh-project-trading`. A breaking change here
  breaks both. Prefer additive changes; deprecate before removing.
- Anything exported from `src/` top-level is public API. Renaming or changing a signature
  requires a note in the PR naming the affected downstream call sites.
- Risk-band and sizing logic is canonical here. Do not fork or re-implement it downstream - if
  a consumer needs different behavior, parameterize it here instead.
- Keep this package dependency-light. New third-party dependencies need justification in the PR.

## Pull requests

- Title in Conventional Commits form.
- Body covers: what changed, why, blast radius, and a test plan as a checklist.
