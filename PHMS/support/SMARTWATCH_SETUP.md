# Smartwatch OAuth and Scheduler Setup

This guide covers environment setup, OAuth provider configuration, migration steps, scheduler behavior, and local verification for smartwatch integration.

## 1. Environment Configuration

Copy env template and set smartwatch values:

```powershell
copy ..\.env.example ..\.env
```

Required keys:

```env
PHMS_BASE_URL=http://127.0.0.1:5000
SMARTWATCH_OAUTH_CALLBACK_PATH=/smartwatch/callback
GOOGLE_FIT_CLIENT_ID=<google-oauth-client-id>
GOOGLE_FIT_CLIENT_SECRET=<google-oauth-client-secret>

ENABLE_SCHEDULER=0
SMARTWATCH_SYNC_INTERVAL_HOURS=6
SMARTWATCH_SYNC_MAX_INSTANCES=1
SMARTWATCH_SYNC_MISFIRE_GRACE_SECONDS=60
SMARTWATCH_SYNC_COALESCE=1

RATELIMIT_SMARTWATCH_AUTH=5 per minute
RATELIMIT_SMARTWATCH_MODIFY=10 per hour
RATELIMIT_SMARTWATCH_SYNC=10 per hour
RATELIMIT_SMARTWATCH_STATUS=30 per minute
```

## 2. OAuth Provider Setup (Google Fit)

Create OAuth credentials in Google Cloud Console and set callback URL to:

```text
<PHMS_BASE_URL><SMARTWATCH_OAUTH_CALLBACK_PATH>
```

Example:

```text
http://127.0.0.1:5000/smartwatch/callback
```

If your app runs behind HTTPS/proxy in production, use your public HTTPS base URL for `PHMS_BASE_URL`.

## 3. Database Migrations

Run migrations before starting app after pulling schema changes:

```powershell
cd PHMS
.\venv\Scripts\Activate.ps1
flask db upgrade
```

This applies smartwatch account/sync tables and health ingestion dedupe fields.

## 4. Runtime and Scheduler Behavior

Runtime wiring is explicit and aligned with `app.py`:

- Importing app module does not auto-start background scheduler.
- `python app.py` runs `bootstrap_background_services()` once.
- Scheduler startup depends on `should_start_scheduler()`.
- For multi-worker production, run scheduler in a dedicated process:

```powershell
set ENABLE_SCHEDULER=1
python app.py
```

Smartwatch periodic sync job uses these env-backed settings:

- `SMARTWATCH_SYNC_INTERVAL_HOURS`
- `SMARTWATCH_SYNC_MAX_INSTANCES`
- `SMARTWATCH_SYNC_MISFIRE_GRACE_SECONDS`
- `SMARTWATCH_SYNC_COALESCE`

## 5. Local Verification

1. Start app:

```powershell
python start.py
```

2. Open Smartwatch page:

```text
http://127.0.0.1:5000/smartwatch
```

3. Validate OAuth flow:
- Click Connect
- Provider consent redirects to callback
- Callback returns to Smartwatch page with status message

4. Validate sync/status APIs:
- Trigger Sync Now in UI
- Check `GET /smartwatch/status/google_fit`

5. Validate tests:

```powershell
python -m pytest tests/smartwatch -q
```

Expected: smartwatch suite passes.
