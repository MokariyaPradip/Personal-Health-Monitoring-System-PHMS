# PHMS Environment Configuration

## Document Metadata
- Purpose: Canonical reference for `.env` variables and runtime configuration behavior.
- Audience: Developers, operators, QA engineers.
- Last Verified: 2026-03-27
- Verified Against: `.env.example`, `PHMS/config.py`, `PHMS/app.py`.
- Source of Truth: Runtime config loading and usage in code.

## Task-Based Navigation
- I need local setup values: [Setup Steps](#setup-steps)
- I need variable meanings: [Variable Reference](#variable-reference)
- I need security/secrets guidance: [Secrets Management](#secrets-management)
- I need smartwatch config: [Smartwatch and OAuth](#smartwatch-and-oauth)
- I need scheduler config: [Scheduler Settings](#scheduler-settings)

## How Configuration Is Loaded
- `.env` is loaded from repository root via `python-dotenv` in `config.py`.
- Template source is `.env.example`.
- If `DATABASE_URL` is unset, app falls back to `PHMS/instance/phms.db`.

## Setup Steps
1. Copy template:
```powershell
copy .env.example .env
```
2. Fill required values.
3. Keep `.env` out of version control.

## Secrets Management
- Never commit production secrets.
- Store secrets in environment/secret manager (not in docs or committed files).
- Rotate `SECRET_KEY` and `SECURITY_PASSWORD_SALT` periodically.
- Use different secret values per environment.

## Critical Production Requirements
- `FLASK_ENV=production`
- `FLASK_DEBUG=0`
- Strong `SECRET_KEY`
- Strong `SECURITY_PASSWORD_SALT`
- Reachable database in `DATABASE_URL`
- Reachable Redis (`REDIS_URL` or host/port/db trio)

Runtime guard:
- Production startup fails if secret key/salt is missing or dev-like.

## Variable Reference

### Flask Runtime
- `FLASK_ENV`: `development|production|testing`
- `FLASK_DEBUG`: `0|1`
- `ENVIRONMENT_NAME`: logging/monitoring label
- `LOG_LEVEL`: `DEBUG|INFO|WARNING|ERROR|CRITICAL`

### Core Security and Session
- `SECRET_KEY`: session signing/encryption key
- `SECURITY_PASSWORD_SALT`: additional cryptographic salt
- `SESSION_COOKIE_SAMESITE`: `Lax|Strict|None`
- `SESSION_COOKIE_SECURE`: `0|1` (secure cookies)
- `FORCE_HTTPS`: `0|1`
- `HSTS_MAX_AGE`: integer seconds
- `HSTS_INCLUDE_SUBDOMAINS`: `0|1`
- `HSTS_PRELOAD`: `0|1`

### Database
- `DATABASE_URL`
  - Example sqlite: `sqlite:///phms.db`
  - Example postgres: `postgresql://user:password@host:5432/phms_db`

Behavior notes:
- `postgres://` is normalized to `postgresql://`.
- Relative sqlite paths are resolved under `PHMS/`.

### Email
- `MAIL_SERVER`
- `MAIL_PORT`
- `MAIL_USE_TLS`
- `MAIL_USE_SSL`
- `MAIL_USERNAME`
- `MAIL_PASSWORD`
- `MAIL_DEFAULT_SENDER`
- `MAIL_SUPPRESS_SEND`

### Rate Limiting and Redis
Redis connectivity:
- `REDIS_URL` (preferred)
- or `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`

Rate limit knobs:
- `RATELIMIT_STORAGE_URL`
- `RATELIMIT_AUTH_ATTEMPTS`
- `RATELIMIT_PASSWORD_RESET`
- `RATELIMIT_REGISTRATION`
- `RATELIMIT_CHANGE_PASSWORD`
- `RATELIMIT_SMARTWATCH_AUTH`
- `RATELIMIT_SMARTWATCH_MODIFY`
- `RATELIMIT_SMARTWATCH_SYNC`
- `RATELIMIT_SMARTWATCH_STATUS`

### Smartwatch and OAuth
- `PHMS_BASE_URL`
- `SMARTWATCH_OAUTH_CALLBACK_PATH`
- `GOOGLE_FIT_CLIENT_ID`
- `GOOGLE_FIT_CLIENT_SECRET`

### Scheduler Settings
- `ENABLE_SCHEDULER`
- `SMARTWATCH_SYNC_INTERVAL_HOURS`
- `SMARTWATCH_SYNC_MAX_INSTANCES`
- `SMARTWATCH_SYNC_MISFIRE_GRACE_SECONDS`
- `SMARTWATCH_SYNC_COALESCE`

### Security Header Variables
- `CONTENT_SECURITY_POLICY`
- `REFERRER_POLICY`
- `PERMISSIONS_POLICY`

### Additional App Flags
- `ENABLE_API`
- `MAX_UPLOAD_SIZE`

## Environment Profiles
### Development
- debug enabled
- sqlite acceptable
- in-memory rate-limit backend fallback acceptable

### Staging
- production-like db/redis recommended
- debug off
- verify callback URLs and scheduler behavior

### Production
- strong secrets
- managed db + redis
- secure cookie + https policy
- dedicated scheduler process strategy

## Needs Verification
- If infrastructure overrides env vars at runtime (container orchestrator), verify final values using runtime logs and effective config inspection.

## See Also
- [README.md](../../README.md)
- [API_REFERENCE.md](API_REFERENCE.md)
- [SMARTWATCH_SETUP.md](SMARTWATCH_SETUP.md)
- [TESTING_GUIDE.md](TESTING_GUIDE.md)
