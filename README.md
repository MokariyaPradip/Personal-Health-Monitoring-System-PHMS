# PHMS - Personal Health Monitoring System

PHMS is a Flask-based health monitoring platform that combines manual health logging, medication tracking, notification workflows, report generation, and smartwatch integration through Google Fit.

This repository is organized with source code under PHMS and project-level configuration/docs at the repository root.

## Table of Contents

- Overview
- Core Features
- Tech Stack
- Repository Structure
- Architecture at a Glance
- Quick Start
- Environment Configuration
- Database and Migrations
- Smartwatch Integration
- Scheduler and Background Jobs
- Running Tests
- Security Notes
- API and Route Areas
- Deployment Notes
- Troubleshooting
- Contributing
- Maintainers and Contact

## Overview

PHMS helps users:

- Track health metrics and risk indicators.
- Manage medications and intake logs.
- Receive alerts and notifications.
- Generate health reports.
- Connect smartwatch data via Google Fit sync.

The system is designed with modular route groups, service and repository layers, and strict ingestion policies for smartwatch data quality.

## Core Features

- Authentication and profile management.
- Health data ingestion and risk scoring.
- ML-assisted health assessment integration.
- Medication CRUD, scheduled logs, and status tracking.
- Notification workflows and alert generation.
- Report pages and PDF report generation.
- Smartwatch OAuth, sync diagnostics, manual sync, and periodic scheduler sync.
- Resilient sync flow with retries and adaptive fetch windows for provider data.

## Tech Stack

- Backend: Flask, Flask-Login, Flask-WTF, Flask-Mail
- Data layer: SQLAlchemy, Flask-Migrate, Alembic
- Scheduler: APScheduler, Flask-APScheduler
- Validation: Pydantic
- ML/Data: scikit-learn, pandas, numpy, scipy, joblib
- Reporting: reportlab, matplotlib
- Security/Rate limiting: Flask-Limiter, Redis (recommended for production)
- Testing: pytest

See dependency pins in [PHMS/requirements.txt](PHMS/requirements.txt).

## Repository Structure

- [instructions.txt](instructions.txt): project-level setup notes.
- [Database](Database): ER docs and database artifacts.
- [PHMS](PHMS): main application package.
- [pytest.ini](pytest.ini): pytest configuration.
- [.env.example](.env.example): environment template.

## Architecture at a Glance

PHMS follows a layered structure:

- Routes layer: feature route registration and HTTP endpoints.
- Controller layer: request transport handling.
- Service layer: business logic orchestration.
- Repository layer: persistence and query operations.
- Model layer: SQLAlchemy entities.
- Jobs layer: scheduled task callbacks.

Route composition starts in [PHMS/routes.py](PHMS/routes.py) and feature registrations in [PHMS/feature_routes/__init__.py](PHMS/feature_routes/__init__.py).

## Quick Start

### Option A: Automated startup (recommended for local)

```powershell
cd PHMS
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python start.py
```

App runs at <http://127.0.0.1:5000>

### Option B: App entrypoint directly

```powershell
cd PHMS
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## Environment Configuration

1. Copy template:

```powershell
copy .env.example .env
```

1. Set at minimum:

```env
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=<strong-random-value>
SECURITY_PASSWORD_SALT=<strong-random-value>
DATABASE_URL=sqlite:///phms.db
```

1. For smartwatch integration:

```env
PHMS_BASE_URL=http://127.0.0.1:5000
SMARTWATCH_OAUTH_CALLBACK_PATH=/smartwatch/callback
GOOGLE_FIT_CLIENT_ID=<google-client-id>
GOOGLE_FIT_CLIENT_SECRET=<google-client-secret>
```

1. For scheduler tuning:

```env
ENABLE_SCHEDULER=0
SMARTWATCH_SYNC_INTERVAL_HOURS=6
SMARTWATCH_SYNC_MAX_INSTANCES=1
SMARTWATCH_SYNC_MISFIRE_GRACE_SECONDS=60
SMARTWATCH_SYNC_COALESCE=1
```

Complete variable documentation is in [.env.example](.env.example).

## Database and Migrations

Run migrations after pulling schema changes:

```powershell
cd PHMS
.\venv\Scripts\Activate.ps1
flask db upgrade
```

SQLite is used by default for local development.

## Smartwatch Integration

Smartwatch setup details are documented in [PHMS/support/SMARTWATCH_SETUP.md](PHMS/support/SMARTWATCH_SETUP.md).

Current integration behavior:

- OAuth via Google Fit.
- Pre-sync diagnostics endpoint to inspect provider metric availability.
- Manual sync endpoint with adaptive lookback and retry behavior.
- Strict ingestion policy for smartwatch payload completeness is enforced downstream.

Important practical note:

- PHMS can only ingest metric families that exist in Google Fit for the connected account.
- Some watch/app combinations (for example Fire-Boltt via Da Fit) may export only partial families (commonly steps).

## Scheduler and Background Jobs

Scheduler bootstrap and policy are in [PHMS/app.py](PHMS/app.py) and [PHMS/jobs/scheduler.py](PHMS/jobs/scheduler.py).

Key behavior:

- Importing app module does not auto-start background scheduler.
- Scheduler starts via explicit bootstrap path.
- In multi-worker setups, run scheduler in a dedicated process.

Dedicated scheduler process example:

```powershell
cd PHMS
set ENABLE_SCHEDULER=1
python app.py
```

## Running Tests

Run full smartwatch-focused suite:

```powershell
cd PHMS
python -m pytest tests/smartwatch -q
```

Run all tests:

```powershell
cd PHMS
python -m pytest -q
```

## Security Notes

- Do not commit .env.
- Use strong random values for SECRET_KEY and SECURITY_PASSWORD_SALT.
- Use Redis-backed rate-limit storage in production.
- Disable debug mode in production.
- Enforce HTTPS in production deployments.

Security-sensitive configuration lives in [PHMS/config.py](PHMS/config.py).

## API and Route Areas

Route families include:

- Auth
- Dashboard
- Profile
- Health
- Medication
- Medication log
- Notifications
- Reports
- Smartwatch

See feature route modules in [PHMS/feature_routes](PHMS/feature_routes).

## Deployment Notes

For production hardening, ensure:

- FLASK_ENV=production
- FLASK_DEBUG=0
- HTTPS/TLS termination and FORCE_HTTPS=1
- Redis configured for rate limiting
- Separate scheduler process for multi-worker app servers
- Environment secrets managed by your platform secret store

## Troubleshooting

1. Smartwatch sync returns incomplete payload:

- Check pre-sync diagnostics for metric_point_totals.
- Verify source app actually writes those metrics to Google Fit.

1. Scheduler appears idle:

- Confirm ENABLE_SCHEDULER policy and active process role.
- Verify periodic job registration in startup logs.

1. OAuth callback issues:

- Verify callback URL exactly matches provider console configuration:
  PHMS_BASE_URL + SMARTWATCH_OAUTH_CALLBACK_PATH

## Contributing

Suggested contribution flow:

1. Create a branch for your change.
2. Keep changes scoped and test-backed.
3. Run relevant pytest suites.
4. Open a pull request with problem statement, approach, and verification notes.

## Maintainers and Contact

Maintainer: MokariyaPradip | Contact: 22ceuog059@ddu.ac.in
