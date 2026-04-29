# Security Policy

## Supported Versions

This project is currently maintained on the default branch and the latest tagged
release line.

| Version | Supported |
|---|---|
| `main` | Yes |
| Latest release | Yes |
| Older releases | No |

## Reporting a Vulnerability

Do not open a public GitHub issue for a security vulnerability.

Use one of these channels instead:

1. GitHub Security Advisories private reporting, if enabled on the repository
2. Email: `mugire.can@example.com`

Include:

- A clear summary of the issue
- Affected file, endpoint, or feature
- Steps to reproduce
- Impact assessment
- Suggested mitigation, if known

## Response Expectations

- Initial acknowledgement target: within 7 days
- Triage target: as soon as the report is validated
- Fix timing depends on severity, exploitability, and release readiness

## Scope

Security-sensitive areas in this project include:

- Camera and RTSP source handling
- Alert delivery credentials and webhook configuration
- Database access and stored event data
- Public API endpoints in `services/typescript/api`
- Any code path that handles uploaded, decoded, or externally sourced media

## Safe Use Notes

- Never commit `.env` files, credentials, camera URLs, or production snapshots
- Treat `data/` as runtime data, not source-controlled content
- Review third-party model and CV dependencies before production deployment
- Keep GitHub Actions dependencies and service base images updated
