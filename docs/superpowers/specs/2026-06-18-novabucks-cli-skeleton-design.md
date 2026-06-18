# novabucks CLI Skeleton Design

## Overview

Bootstrap a CLI Python application named "novabucks" that will sign Maven artifacts. This spec covers the initial project skeleton — no signing logic yet, just the scaffolding.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Python version | 3.11+ | Matches RHEL 9 / UBI 9 baseline |
| CLI framework | argparse (stdlib) | Zero runtime dependencies for a pipeline tool |
| Build system | pyproject.toml + setuptools | Standard PEP 621, no extra tooling |
| Project layout | src layout | Prevents import shadowing, packaging best practice |
| Test framework | pytest | De facto standard, rich fixtures and plugins |
| Linter/formatter | ruff | Fast, single tool for linting and formatting |
| Container image | Deferred | No Containerfile until the tool has real functionality |

## Project Structure

```
novabucks/                          # repo root
├── src/
│   └── novabucks/
│       ├── __init__.py             # __version__ = "0.1.0"
│       ├── __main__.py             # enables `python -m novabucks`
│       └── cli.py                  # argparse CLI with subcommand scaffolding
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # shared pytest fixtures (empty initially)
│   └── test_cli.py                 # CLI smoke tests
├── pyproject.toml                  # PEP 621 metadata, setuptools, console_scripts, tool config
├── .gitignore                      # Python-specific ignores
├── .gitlab-ci.yml                  # existing SAST/Secret Detection CI (preserved)
└── README.md                       # replaced with real project documentation
```

## CLI Architecture

### Entry Points

- `novabucks` command via `[project.scripts]` in pyproject.toml, pointing to `novabucks.cli:main`
- `python -m novabucks` via `__main__.py`

### Subcommand Pattern

```
novabucks --version              # prints version, exits 0
novabucks sign [args...]         # placeholder subcommand, prints "not yet implemented", exits 1
novabucks                        # no subcommand: prints help, exits 2
```

### Module Design

**`cli.py`:**
- `create_parser() -> ArgumentParser` — builds the argument parser with a subparsers group. Registers `sign` as a placeholder subcommand.
- `main(argv: list[str] | None = None) -> None` — parses args (defaults to `sys.argv[1:]`), dispatches to subcommand handler. The `argv` parameter enables direct testing without subprocess calls.

**`__main__.py`:**
- Calls `cli.main()`, nothing else.

**`__init__.py`:**
- Defines `__version__ = "0.1.0"`.

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Operation failed (not implemented, future signing errors) |
| 2 | Usage error (no subcommand, bad arguments) |

## Packaging (pyproject.toml)

- **Build backend:** setuptools
- **Metadata:** PEP 621 — name, version, description, python_requires >= 3.11, license
- **Console script:** `novabucks = "novabucks.cli:main"`
- **Dev dependencies:** pytest, ruff (declared in `[project.optional-dependencies]` under a `dev` extra)
- **Tool config:** `[tool.pytest.ini_options]` and `[tool.ruff]` sections inline

## Testing

Using pytest with tests under `tests/`.

### Initial Test Cases

| Test | Description |
|------|-------------|
| `test_version_flag` | `--version` prints version string and exits 0 |
| `test_no_subcommand_shows_help` | No arguments prints help and exits 2 |
| `test_sign_not_implemented` | `sign` subcommand prints "not yet implemented" and exits 1 |

All tests call `main(argv=[...])` directly — no subprocess overhead.

## Dev Tooling

### Ruff Configuration

- Target: Python 3.11
- Line length: 120
- Rule sets: E (pycodestyle errors), F (pyflakes), W (pycodestyle warnings), I (isort)

### .gitignore

Standard Python ignores: `__pycache__/`, `*.pyc`, `.eggs/`, `*.egg-info/`, `dist/`, `build/`, `.venv/`, `.pytest_cache/`, `.ruff_cache/`

## Out of Scope

- Signing logic (future work)
- Key management (future work)
- Containerfile / container image build (deferred)
- CI pipeline stages for testing/linting (can be added later to .gitlab-ci.yml)
