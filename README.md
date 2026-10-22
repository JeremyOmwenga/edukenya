# EduKenya
An AI-Augmented Learning Platform for the Competency Based Curriculum
This platform aims to boost mastery of concepts as building blocks. There is a massive gap in transition between the old 8-4-4 curriculum and the new CBC and this aims to supplement instructor-led eduction by providing a reliable means for students to read and answer questions that gauge their understanding. Teachers can be able to monitor students' progress and intervene immediately and progress can be monitored effectively through visual dashboards. 
The ideal for this project is to avoid morphing into a record-based academic management system. I do not intend for this project to be a repository for viewing exam records or downloading PowerPoints and PDFs of class notes. Rather, it will be built from the ground up to focus on competency and mastery of content as a foundation for more rigorous concepts as a student progresses.

## Development progress
See [DEVLOG.md](DEVLOG.md) for a timestamped log of every feature, the reasoning behind it, and the security guardrails in place.

## Local setup (Windows)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pre-commit install
Copy-Item .env.example .env              # then fill in values (DB password, SES keys)
.\scripts\setup_local_db.ps1             # creates the local Postgres role + database
python manage.py migrate_schemas --shared
python manage.py createcachetable
python manage.py bootstrap_public        # maps the root domain to the platform
python manage.py createsuperuser         # your super admin account (public schema)
python scripts\compile_messages.py
python manage.py runserver
```
- Landing page: http://localhost:8000
- Super admin console: http://localhost:8000/console/
- An approved school: http://<subdomain>.localhost:8000

Tests: `python manage.py test tests`

## Guides
- AWS SES (email): [docs/aws/01-ses.md](docs/aws/01-ses.md)
- GitHub guardrails: [docs/devops/github.md](docs/devops/github.md)
