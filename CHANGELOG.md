# Changelog

All notable changes to this project should be documented in this file.

The format is based on Keep a Changelog and the project uses semantic version
tags such as `v0.1.0`.

## [Unreleased]

### Added

- GitHub process files: `CODEOWNERS`, Dependabot, issue forms, PR template
- Tag-based GitHub release workflow
- Security policy
- Changelog
- Camera health monitoring alerts
- Facility-fault and threat label mapping for custom CV models
- Fallen-person behavior detection

### Changed

- Simplified project documentation into a single main `README.md`
- Hardened CI to run project-defined test, lint, and security checks
- Split heavy CV dependencies into optional `vision` extras in `pyproject.toml`
- Simplified `requirements.txt` to install from project metadata

### Removed

- Checked-in runtime SQLite database
- Duplicated Markdown documentation files
- Local/generated clutter from the repo baseline

## [0.1.0] - 2026-04-26

### Added

- Initial published baseline for the AI security camera system
- Python detection pipeline with alerts, dashboard, attendance, and persistence
- Optional Go, TypeScript, and Rust service layout
- Automated tests and GitHub CI
