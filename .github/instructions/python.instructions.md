---
applyTo: "**/*.py"
---

# Python

- Target `requires-python = ">=3.12"`. Do not use syntax newer than 3.12.
- Full type annotations, including return types. Use `from __future__ import annotations`
  where it keeps signatures readable.
- Prefer `pathlib.Path` over `os.path`, f-strings over `%`/`.format()`,
  `dataclasses` over ad-hoc dicts for structured data.
- This package uses **`requests`** (a declared dependency, used in `src/`). Use it. Do not introduce `httpx` or another HTTP client without adding the dependency and raising it in the PR.
- Exceptions: raise specific types, never bare `except:`. `except Exception` requires a
  logged reason and a comment explaining why it is safe to continue.
- Immutability: return new lists/dicts/dataclasses rather than mutating inputs.
  `dataclasses.replace()` and `{**old, "k": v}` are preferred over in-place edits.
- Logging: module-level `logger = logging.getLogger(__name__)`. Never `print()` in library code.
  Never log secrets, tokens, or personally identifying data.
- Run `ruff check --fix` and `ruff format` on anything you touch.
