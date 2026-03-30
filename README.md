# PHMS - Personal Health Monitoring System

PHMS is a Flask-based web application for personal health tracking, medication management, notifications, reporting, and smartwatch (Google Fit) synchronization.

This repository is structured as a final-year college project with code, tests, architecture/design diagrams, and implementation/testing evidence.

## Project Scope

- Educational software engineering project.
- Demonstrates layered backend architecture, scheduling, ML-assisted risk evaluation, and OAuth integration.
- Not intended as a certified medical system.

## Core Features

- User authentication, session management, and OTP-based password reset.
- Profile management with BMI and health context updates.
- Health metric ingestion (manual and smartwatch-origin data) with validation.
- ML-assisted health risk assessment pipeline.
- Medication CRUD and medication-log lifecycle tracking (`pending/taken/missed/skipped`).
- Notification center plus email-based critical alerts.
- Report generation (weekly/monthly/yearly/custom) including PDF export.
- Smartwatch OAuth connect/disconnect, diagnostics, manual sync, and periodic scheduler sync.

## Technology Stack

- Backend: Flask, Flask-Login, Flask-WTF, Flask-Mail
- Data: SQLAlchemy, Flask-Migrate, Alembic
- Scheduling: APScheduler, Flask-APScheduler
- Validation: Pydantic
- ML/Data: scikit-learn, pandas, numpy, scipy, joblib
- Reporting: reportlab, matplotlib
- Security/Rate limiting: Flask-Limiter (Redis recommended in production)
- Testing: pytest

Dependencies are pinned in [PHMS/requirements.txt](PHMS/requirements.txt).

## Repository Layout

- [PHMS](PHMS): main application source code.
- [PHMS/tests](PHMS/tests): automated tests.
- [PHMS/support](PHMS/support): API/testing/env/smartwatch and implementation guides.
- [Diagrams](Diagrams): architecture, UML, DFD, flow, sequence, state-machine, and UI evidence assets.
- [instructions.txt](instructions.txt): project setup notes.
- [pytest.ini](pytest.ini): pytest discovery and path configuration.
- [.env.example](.env.example): environment variable template.

## Architecture Summary

PHMS follows a layered composition:

1. Routes (`PHMS/feature_routes/*`) register endpoints by feature module.
2. Controllers (`PHMS/controllers/*`) handle HTTP transport and response shape.
3. Services (`PHMS/services/*`) hold business logic and orchestration.
4. Repositories (`PHMS/repositories/*`) centralize persistence queries.
5. Models (`PHMS/models/*`) define SQLAlchemy entities.
6. Jobs (`PHMS/jobs/*`) host scheduler task callbacks.

Route composition entrypoints:

- [PHMS/routes.py](PHMS/routes.py)
- [PHMS/feature_routes/__init__.py](PHMS/feature_routes/__init__.py)

## Diagram Coverage

This repository includes a complete design trail from analysis to validation.

- Root draw.io + PNG diagrams:
  - `PHMS Architecture Diagram`
  - `PHMS Class Diagram`
  - `PHMS Final ER Diagram`
  - `PHMS Usecase Diagram`
- DFD diagrams: [Diagrams/DFD_Diagrams](Diagrams/DFD_Diagrams)
- Flow diagrams: [Diagrams/Flow_Diagrams](Diagrams/Flow_Diagrams)
- Sequence diagrams: [Diagrams/Sequence_Diagrams](Diagrams/Sequence_Diagrams)
- State machines: [Diagrams/State_Machine_Diagrams](Diagrams/State_Machine_Diagrams)
- Mermaid source mirrors of outer diagrams: [Diagrams/Repeat_Outer_Diagrams](Diagrams/Repeat_Outer_Diagrams)
- Chapter-wise visual evidence/output captures:
  - [Diagrams/UI Output/Chapter_4_Requirement_Analysis](Diagrams/UI%20Output/Chapter_4_Requirement_Analysis)
  - [Diagrams/UI Output/Chapter_5_System_Design](Diagrams/UI%20Output/Chapter_5_System_Design)
  - [Diagrams/UI Output/Chapter_6_System_Implementation](Diagrams/UI%20Output/Chapter_6_System_Implementation)
  - [Diagrams/UI Output/Chapter_7_Testing_and_Validation](Diagrams/UI%20Output/Chapter_7_Testing_and_Validation)

## Quick Start (Windows PowerShell)

```powershell
cd PHMS
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Application URL: <http://127.0.0.1:5000>

Alternative manual entrypoint:

```powershell
cd PHMS
python start.py
```

## Environment Configuration

1. Copy template:

```powershell
copy .env.example .env
```

1. Set baseline values:

```env
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=<strong-random-value>
SECURITY_PASSWORD_SALT=<strong-random-value>
DATABASE_URL=sqlite:///phms.db
```

1. Smartwatch OAuth keys (required for connect/sync):

```env
PHMS_BASE_URL=http://127.0.0.1:5000
SMARTWATCH_OAUTH_CALLBACK_PATH=/smartwatch/callback
GOOGLE_FIT_CLIENT_ID=<google-client-id>
GOOGLE_FIT_CLIENT_SECRET=<google-client-secret>
```

1. Scheduler settings:

```env
ENABLE_SCHEDULER=0
SMARTWATCH_SYNC_INTERVAL_HOURS=6
SMARTWATCH_SYNC_MAX_INSTANCES=1
SMARTWATCH_SYNC_MISFIRE_GRACE_SECONDS=60
SMARTWATCH_SYNC_COALESCE=1
```

For full variable reference, see:

- [.env.example](.env.example)
- [PHMS/support/ENVIRONMENT_CONFIGURATION.md](PHMS/support/ENVIRONMENT_CONFIGURATION.md)

## Database and Migrations

Run migrations after pulling schema changes:

```powershell
cd PHMS
.\venv\Scripts\Activate.ps1
flask db upgrade
```

Default local database is SQLite.

## Scheduler and Background Jobs

Scheduler startup policy is defined in [PHMS/app.py](PHMS/app.py) and jobs are wired in [PHMS/jobs/scheduler.py](PHMS/jobs/scheduler.py).

Verified behavior:

- Importing modules does not auto-start the scheduler.
- Background bootstrap is explicit.
- In multi-worker production, run scheduler in one dedicated process.

Dedicated scheduler process example:

```powershell
cd PHMS
set ENABLE_SCHEDULER=1
python app.py
```

## Smartwatch Integration Notes

- Provider flow is Google Fit OAuth.
- Pre-sync diagnostics endpoint is available to inspect metric availability.
- Manual and periodic sync both rely on provider-side data availability.
- Some device/app combinations may export only partial metric families.

Detailed guide: [PHMS/support/SMARTWATCH_SETUP.md](PHMS/support/SMARTWATCH_SETUP.md)

## Testing

Test configuration:

- Runner: `pytest`
- Config: [pytest.ini](pytest.ini)
- Discovery root: `PHMS/tests`

Run all tests:

```powershell
python -m pytest -q
```

Run smartwatch suite:

```powershell
python -m pytest PHMS/tests/smartwatch -q
```

Canonical testing documentation: [PHMS/support/TESTING_GUIDE.md](PHMS/support/TESTING_GUIDE.md)

## API and Modules Reference

- API contract: [PHMS/support/API_REFERENCE.md](PHMS/support/API_REFERENCE.md)
- Medication-log system guide: [PHMS/support/MEDICATION_LOG_SYSTEM_COMPREHENSIVE_GUIDE.md](PHMS/support/MEDICATION_LOG_SYSTEM_COMPREHENSIVE_GUIDE.md)
- ML model/runtime notes: [PHMS/support/ML_MODEL_GUIDE.md](PHMS/support/ML_MODEL_GUIDE.md)
- Architecture migration playbook: [PHMS/support/ARCHITECTURE_INCREMENTAL_MIGRATION_PLAYBOOK.md](PHMS/support/ARCHITECTURE_INCREMENTAL_MIGRATION_PLAYBOOK.md)

## Known Limitations

- Health risk outputs are decision-support signals, not medical diagnosis.
- Smartwatch ingestion can only process metrics available from the provider/account.
- Email delivery depends on SMTP provider reliability and configuration.
- No committed CI workflow under `.github/workflows` at this time.

## Contributing

1. Create a feature/fix branch.
2. Keep changes scoped and test-backed.
3. Run relevant pytest suites.
4. Open a pull request with problem statement, approach, and verification notes.

## Maintainer

- Name: MokariyaPradip
- Contact: 22ceuog059@ddu.ac.in
