# AGENTS.md

Guidance for coding agents working in this repository.

## Scope

- Primary runtime is Python (`main.py`, `src/`, `config/`, `scripts/`, `tests/`).
- Optional polyglot services live under `services/` (Go, TypeScript, Rust) and are not required for core Python demo mode work.

## Key Paths

- `src/pipeline.py`: top-level processing pipeline
- `src/camera/`: camera feed management
- `src/detection/`: detectors and post-processing
- `src/alerts/`: alert dispatch logic
- `src/database/`: SQLAlchemy models and persistence
- `src/dashboard/`: terminal/dashboard output
- `tests/`: Python test suite

## Environment and Setup

- Python requirement: `>=3.10`
- Test dependencies: `python -m pip install -e .[test]`
- Dev dependencies: `python -m pip install -e .[dev]`

## Local Quality Commands

Use `Taskfile.yml` tasks when available:

- `task test` → `python -m pytest tests -q`
- `task lint` → flake8 + black --check + isort --check-only
- `task security` → `python -m bandit -r config src scripts main.py`
- `task evaluation:validate` → evaluation manifest check
- `task ci` → test + lint + security + evaluation validation

If `task` is unavailable, run the Python commands directly from `Taskfile.yml`.

## Change Rules

- Keep changes minimal and targeted to the request.
- Add or update tests when behavior changes.
- Update `README.md` if user-facing behavior or workflow changes.
- Do not commit runtime artifacts under `data/`.
- Never commit secrets; use `.env.example` as the template for env vars.

## Security and Config Notes

- Security reporting guidance is in `SECURITY.md`.
- Main runtime configuration is driven by `.env` (copy from `.env.example`).
- Important API/auth controls include `API_AUTH_ENABLED`, `API_KEYS`, `CORS_ORIGIN`, and `TRUST_PROXY`.
