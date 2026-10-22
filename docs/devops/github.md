# GitHub guardrails (one-time setup)

Goal: nothing reaches `main` (and later, production) without passing CI and
being reviewed. Do this once in the GitHub website.

## 1. Protect `main`
Repo > **Settings** > **Rules** > **Rulesets** > **New ruleset** > **New branch ruleset**
- Name: `protect-main`. Enforcement status: **Active**.
- Target branches: **Add target** > **Include default branch**.
- Tick:
  - **Restrict deletions**
  - **Block force pushes**
  - **Require a pull request before merging** (required approvals: 0 while you work solo, raise it when someone joins)
  - **Require status checks to pass** > **Add checks** > choose `checks` (it appears after CI has run once) and tick **Require branches to be up to date**
- **Create**.

## 2. Turn on secret and dependency protection
Repo > **Settings** > **Advanced Security** (called "Code security" on some accounts):
- **Dependabot alerts**: Enable
- **Dependabot security updates**: Enable
- **Secret Protection** / **Secret scanning**: Enable, and enable **Push protection** (GitHub refuses pushes that contain known secret formats)

## 3. Your account
- Profile picture > **Settings** > **Password and authentication** > enable **two-factor authentication**. Whoever controls this GitHub account controls the code that will run in production.

## 4. Local hooks (each machine)
```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pre-commit install
```
After this, `git commit` scans for secrets and blocks direct commits to `main`.
