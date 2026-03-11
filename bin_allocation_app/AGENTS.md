# AGENTS.md

Operational guide for coding agents working in `bin_allocation_app`.

## Repository Snapshot
- Stack: Python + Streamlit + Pandas + Plotly.
- Entry point: `app.py`.
- Dependency manifest: `requirements.txt`.
- Test suite: not currently present in repo (no `tests/` yet).
- Build artifact pipeline: none (runtime app, not packaged library).

## Rule Files Check (Cursor / Copilot)
- Checked `.cursor/rules/`: not found in this repository.
- Checked `.cursorrules`: not found in this repository.
- Checked `.github/copilot-instructions.md`: not found in this repository.
- If any of these files are added later, treat them as high-priority instructions.

## Environment Setup
- Create venv: `python3 -m venv .venv`
- Activate venv (macOS/Linux): `source .venv/bin/activate`
- Install deps: `pip install -r requirements.txt`
- Run app locally: `streamlit run app.py`

## Build / Run Commands
- There is no compile/bundle build step in this project.
- Primary run command: `streamlit run app.py`
- Quick syntax validation: `python -m py_compile app.py`
- Broader import/syntax validation: `python -m compileall .`

## Lint / Format / Type Commands
Use these when tools are available in your environment.

- Lint (recommended): `ruff check .`
- Auto-fix lint issues: `ruff check . --fix`
- Format (recommended): `ruff format .` or `black .`
- Type-check (optional): `mypy app.py`

Notes:
- `ruff`, `black`, and `mypy` are not currently pinned in `requirements.txt`.
- If a command is missing, install tool locally or skip with clear note in PR/report.

## Test Commands
Current state: no committed tests discovered.

When adding tests, prefer `pytest`.

- Run all tests: `pytest`
- Run with verbose output: `pytest -vv`
- Run a single file: `pytest tests/test_app.py`
- Run a single test function: `pytest tests/test_app.py::test_build_mapped_df`
- Run a single test class: `pytest tests/test_app.py::TestStatusDerivation`
- Run tests matching keyword: `pytest -k "status and not slow"`
- Stop on first failure: `pytest -x`

If using stdlib `unittest` instead:
- Run all: `python -m unittest discover -s tests -p "test_*.py"`
- Run one test: `python -m unittest tests.test_app.TestStatusDerivation.test_disabled_when_blocked`

## Expected Project Layout
- Keep app entry in `app.py` unless doing a deliberate refactor.
- If code grows, extract pure helpers into modules (for easier testing).
- Add tests under `tests/` with `test_*.py` names.
- Keep sample data or fixtures out of root when possible (`tests/fixtures/`).

## Code Style Guidelines

### Imports
- Group imports in this order: stdlib, third-party, local modules.
- Keep one import per line unless strongly related.
- Prefer explicit imports over wildcard imports.
- Preserve stable import ordering to reduce noisy diffs.

### Formatting
- Follow PEP 8 defaults (4-space indent, line length ~88-100).
- Use consistent trailing commas in multiline literals/calls when helpful.
- Keep functions short and focused; split large blocks into helpers.
- Avoid unnecessary comments; prefer clear names and small functions.

### Types
- Add type hints on all new function signatures.
- Keep return types explicit (`-> pd.DataFrame`, `-> None`, etc.).
- Use `Optional[T]` only when `None` is a real value path.
- Prefer concrete container types in signatures when practical.

### Naming
- `snake_case` for functions/variables.
- `UPPER_SNAKE_CASE` for constants and mapping tables.
- Use clear domain names (`storage_section`, `disabled_reason`) over abbreviations.
- Boolean names should read as predicates (`is_empty`, `has_block`).

### DataFrame and Transformation Patterns
- Keep normalization/derivation logic deterministic and side-effect free.
- Prefer vectorized operations; use row-wise `apply` only when needed.
- Normalize text/columns once, then reuse canonical values.
- Avoid mutating shared DataFrames across unrelated concerns.
- Use `safe_number`-style helpers for numeric coercion paths.

### Streamlit Patterns
- Keep UI composition in render functions (`kpi_row`, `render_charts`, etc.).
- Keep data loading and transformation separate from rendering.
- Use `@st.cache_data` for expensive/IO-heavy read operations.
- Fail fast for missing required inputs and stop rendering early.

### Error Handling
- Catch expected file parsing errors explicitly when possible.
- Show user-facing errors with actionable wording (`st.error`, `st.warning`, `st.info`).
- Avoid broad exceptions unless reporting context clearly.
- Return early after unrecoverable UI-state errors.
- Do not silently swallow exceptions.

### Constants and Configuration
- Centralize stable mappings/constants near top of module.
- Prefer dictionaries for normalization maps over branching chains.
- Keep color/status/type maps synchronized with UI labels.
- Avoid hardcoded machine-specific paths in new code; prefer config/env.

### Testing Guidance for New Work
- Prioritize pure-function tests for:
  - `normalize_*` helpers,
  - status/bin derivation,
  - mapping defaults and coercion.
- Add regression tests for parsing edge cases (CSV delimiters, missing columns).
- For DataFrame assertions, compare both shape and key column values.
- Keep tests independent from Streamlit UI where possible.

### Git and Change Hygiene
- Make minimal, scoped edits; avoid unrelated refactors.
- Preserve backward behavior unless requirement explicitly changes it.
- If introducing tooling (ruff/pytest/mypy), update docs and dependency files.
- Document any new command in this file and in `README.md` when user-facing.

## Agent Execution Checklist
- Confirm venv and dependencies are installed.
- Run relevant lint/format/type/test commands for touched code.
- For no-test repos, at least run syntax checks before finalizing.
- Include exact commands run and outcomes in your final report.
- If a required tool is unavailable, report it and provide fallback verification.

## Priority of Instructions
- Direct user instruction
- Repository rule files (`.cursor/rules/`, `.cursorrules`, `.github/copilot-instructions.md`) when present
- This `AGENTS.md`
- General language/framework conventions
