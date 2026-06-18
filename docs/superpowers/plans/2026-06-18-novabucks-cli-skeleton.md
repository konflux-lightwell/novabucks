# novabucks CLI Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap the novabucks Python CLI project with src layout, argparse-based subcommand scaffolding, and a working test suite.

**Architecture:** A `src/novabucks/` package with a `cli.py` module that uses argparse with subparsers for future extensibility. A `sign` placeholder subcommand demonstrates the pattern. Entry points via `console_scripts` and `__main__.py`.

**Tech Stack:** Python 3.11+, argparse (stdlib), setuptools, pytest, ruff

## Global Constraints

- Python >= 3.11
- Zero runtime dependencies (stdlib only)
- src layout (`src/novabucks/`)
- Build backend: setuptools
- Line length: 120
- Ruff rules: E, F, W, I
- Commit trailers must include `Assisted-by: Claude`

---

### Task 1: Project Configuration & Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/novabucks/__init__.py`
- Create: `src/novabucks/__main__.py`
- Create: `src/novabucks/cli.py` (empty placeholder)
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: nothing
- Produces: installable package (`pip install -e ".[dev]"`), `novabucks.__version__` string

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "novabucks"
version = "0.1.0"
description = "CLI tool for signing Maven artifacts"
requires-python = ">=3.11"
license = "Apache-2.0"

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "ruff>=0.4",
]

[project.scripts]
novabucks = "novabucks.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
target-version = "py311"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "W", "I"]
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
__pycache__/
*.pyc
*.pyo
*.egg-info/
*.egg
.eggs/
dist/
build/
.venv/
.pytest_cache/
.ruff_cache/
```

- [ ] **Step 3: Create `src/novabucks/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Create `src/novabucks/__main__.py`**

```python
from novabucks.cli import main

main()
```

- [ ] **Step 5: Create `src/novabucks/cli.py` (minimal placeholder)**

```python
def main(argv=None):
    pass
```

This is a placeholder so the package is installable. Task 2 replaces it with the real implementation.

- [ ] **Step 6: Create `tests/__init__.py`**

Empty file.

- [ ] **Step 7: Create `tests/conftest.py`**

Empty file.

- [ ] **Step 8: Replace `README.md`**

```markdown
# novabucks

CLI tool for signing Maven artifacts.

## Installation

```bash
pip install -e ".[dev]"
```

## Usage

```bash
novabucks --version
novabucks sign
```

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check src/ tests/
```
```

- [ ] **Step 9: Install the package in dev mode and verify**

Run: `pip install -e ".[dev]"`
Expected: successful install, `novabucks` command available

Run: `python -c "from novabucks import __version__; print(__version__)"`
Expected: `0.1.0`

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml .gitignore src/ tests/ README.md
git commit -m "Add project scaffolding with src layout and pyproject.toml

Assisted-by: Claude"
```

---

### Task 2: CLI Implementation (TDD)

**Files:**
- Create: `tests/test_cli.py`
- Modify: `src/novabucks/cli.py`

**Interfaces:**
- Consumes: `novabucks.__version__` from `src/novabucks/__init__.py`
- Produces: `create_parser() -> argparse.ArgumentParser`, `main(argv: list[str] | None = None) -> None`

- [ ] **Step 1: Write failing tests in `tests/test_cli.py`**

```python
import pytest

from novabucks.cli import main


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "0.1.0" in captured.out


def test_no_subcommand_exits_with_code_2(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2


def test_sign_not_implemented(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["sign"])
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "not yet implemented" in captured.err
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`
Expected: all 3 tests FAIL (the placeholder `main` doesn't parse args or raise `SystemExit`)

- [ ] **Step 3: Implement `src/novabucks/cli.py`**

```python
import argparse
import sys

from novabucks import __version__


def _handle_sign(_args):
    print("sign: not yet implemented", file=sys.stderr)
    raise SystemExit(1)


def create_parser():
    parser = argparse.ArgumentParser(prog="novabucks", description="CLI tool for signing Maven artifacts")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("sign", help="Sign Maven artifacts")

    return parser


def main(argv=None):
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        raise SystemExit(2)

    handlers = {
        "sign": _handle_sign,
    }
    handlers[args.command](args)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Run ruff to verify code quality**

Run: `ruff check src/ tests/`
Expected: no errors

- [ ] **Step 6: Verify CLI entry points manually**

Run: `novabucks --version`
Expected: `novabucks 0.1.0`

Run: `python -m novabucks --version`
Expected: `novabucks 0.1.0`

Run: `novabucks sign`
Expected: `sign: not yet implemented` on stderr, exit code 1

Run: `novabucks`
Expected: help text printed, exit code 2

- [ ] **Step 7: Commit**

```bash
git add src/novabucks/cli.py tests/test_cli.py
git commit -m "Implement argparse CLI with sign placeholder subcommand

Assisted-by: Claude"
```
