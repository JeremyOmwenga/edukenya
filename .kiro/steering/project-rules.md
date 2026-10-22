# EduKenya project rules

## Development log
- Every feature that is committed for a push MUST add a new entry at the top of `DEVLOG.md` (newest first) before committing.
- Entry heading format: `## YYYY-MM-DD HH:MM EAT · <feature name>` using the real current time in East Africa Time (UTC+3), plus the branch name.
- Use the sections: What, Why / logic, Security, Verified, Ops (manual steps for the user), Next. Keep it plain language; the owner is not an AWS expert.

## Security baseline (production-bound system)
- Never weaken: tenant isolation (schema per school), host-only cookies, the inactive-tenant block in `tenancy/middleware.py`, the production guardrails at the bottom of `edukenya/settings.py`, CSP without `unsafe-inline`.
- Every state-changing endpoint is POST + CSRF and checks authorization server-side. Unknown/forbidden resources return 404, not 403, where existence itself is sensitive.
- New auth/login/registration endpoints must be rate limited (`edukenya.security.rate_limited`) and must not reveal whether an account exists.
- Privileged actions are recorded with `console.audit.record`.
- Secrets only via environment variables. Never commit `.env`, never print secrets in output.
- Add tests for every new security guarantee in `tests/`.
- Pin dependency versions exactly; run `pip-audit` after adding one.

## Conventions
- UI copy: short, friendly, no em dashes, bright palette. Every user-facing string is translatable and has a Kiswahili entry (`python scripts/make_messages.py`, then compile with `scripts/compile_messages.py`). Console (platform owner only) is English.
- Infra is CloudFormation in `infra/cloudformation/`, region eu-west-1, with a step-by-step console guide in `docs/aws/`.
- Work on feature branches; `main` is protected.
