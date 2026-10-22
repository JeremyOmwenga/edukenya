# EduKenya development log

A running record of every feature pushed: what it does, why it is built the
way it is, and how it was verified. Newest entry first. Times are East Africa
Time (EAT, UTC+3).

Each entry uses the same headings:
**What** (the feature), **Why / logic** (design decisions), **Security**
(guardrails added), **Verified** (tests and checks run), **Ops** (anything you
must do by hand, e.g. in AWS or Cloudflare), **Next**.

---

## 2026-10-22 12:15 EAT · School registration, approval console and tenant isolation
Branch: `feature/school-registration`

**What**
- "Register your school" flow on the root domain: school name, 8 digit KNEC code, county, web address (subdomain), admin name, email and password.
- Email verification through Amazon SES. The link expires after 48 hours, works once, and has to be confirmed with a button press.
- Super admin console at `/console/` on the root domain: overview, applications (approve, or reject with a written reason that is emailed to the admin), schools (suspend or reactivate with a reason), and an audit log.
- On approval the platform creates the school's own PostgreSQL schema and its subdomain (`<name>.headybegone.dpdns.org`), moves the admin account into it, and emails the admin a sign in link.
- School sites: sign in, sign out, and a placeholder dashboard.
- Kiswahili for every public and school page and every email. The console stays English.

**Why / logic**
- *Multi-tenancy, one schema per school* (django-tenants). Every school's data, including its users and sessions tables, lives in its own schema. A query running for school A cannot see school B's rows because they are in a different schema, not just filtered by a column someone could forget.
- *Nothing exists until approval.* An application lives only in the public schema. No schema, domain or user is created until the super admin approves it. Unapproved, pending and rejected schools have no website at all.
- *Approval is one database transaction.* PostgreSQL DDL is transactional, so if any step fails (schema, domain, admin user), all of it rolls back.
- *Passwords*: hashed with Argon2 at registration. On approval the hash is copied into the school's users table and wiped from the application record.
- *Students without email*: the `User` model already allows email to be empty for students (enforced by a database constraint), ready for the admission number + PIN flow.

**Security**
- Host header: only `headybegone.dpdns.org` and its subdomains are accepted. Any other host gets a bare 404. Unknown, suspended and pending subdomains all return the same 404, so nobody can probe which schools exist.
- Suspension: the tenant middleware blocks every request to a non-active school before any view runs. This is the switch for unpaid subscriptions later.
- Sessions: cookies are host-only, so a session on one school's site is never sent to another. Even a copied cookie fails, because each school has its own sessions table (covered by a test).
- Console: works only on the root domain, only for active platform super admins. Anyone else gets "incorrect email or password" or a 404. All state changes are POST with CSRF protection. Logins, failed logins, approvals, rejections and suspensions are written to an append-only audit log.
- No account enumeration: registering with an email that is already in use shows the same page and sends a notice to that address instead. Resend always shows the same message. The duplicate path still runs the password hash, so the response time matches the normal path.
- Rate limits (database-backed, per IP and per account): registration, resend, school login, console login.
- Honeypot field on registration to drop simple bots.
- Subdomain rules: 3 to 30 characters, no `--` (blocks punycode look-alikes), and a reserved list (`www`, `mail`, `admin`, `console`, `api`, ...).
- Headers: Content Security Policy (no inline scripts), `X-Frame-Options: DENY`, `nosniff`, a strict referrer policy and a permissions policy. `Cache-Control: no-store` on signed-in pages. HSTS for one year including subdomains in production.
- `django.contrib.admin` is not installed at all (less attack surface).
- Production guardrails: with `DJANGO_DEBUG` off, the app refuses to start if the secret key is weak, the domain is still localhost, HTTPS is off, the DB password is missing, DB TLS is off, or email is set to a fake backend. `DEBUG` now defaults to off.
- Repo guardrails: pre-commit hooks scan for secrets (gitleaks), block `.env` files and private keys, block direct commits to `main`, lint CloudFormation and require complete translations. CI runs the same hooks plus tests, `pip-audit`, a missing-migration check and `check --deploy`.

**Verified**
- 36 automated tests (registration, verification, approval, isolation between schools, suspension, console access, rate limits, Kiswahili pages and emails, production refusal to boot).
- `manage.py check --deploy` with production settings: clean (the HSTS preload warning is silenced on purpose).
- `pip-audit`: no known vulnerabilities. `cfn-lint`: clean.

**Ops (your to-do)**
1. Local DB: run `.\scripts\setup_local_db.ps1` (asks for the `postgres` password), then the migrate commands in README.
2. SES: follow `docs/aws/01-ses.md` with domain `headybegone.dpdns.org`.
3. GitHub: turn on branch protection as described in `docs/devops/github.md`.

**Next**
- MFA (authenticator app) for the console. This is the most valuable account on the platform.
- Role sign up on school subdomains (teachers, parents) and the admission-number roster for students.

---

## 2026-10-22 10:56 EAT · Landing page (`91a6c41`)

**What**: rebuilt the project as Django 5.2 with a bilingual (English/Kiswahili) landing page for Junior School learners. It explains CBC-scoped RAG, content regeneration, mastery tests per concept, the cross-grade knowledge graph, and the school features (grades, assignments, fees, student info).

**Why / logic**: server-rendered Django templates with no JavaScript, so it is fast on low-end phones. Bright palette with AA contrast. Django i18n, so the toggle is remembered per visitor.

**Verified**: every string has a Kiswahili translation, the toggle switches language, and there are no em dashes.
