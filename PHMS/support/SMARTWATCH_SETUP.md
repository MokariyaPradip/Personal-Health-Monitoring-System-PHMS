# Smartwatch OAuth and Sync Setup

## Document Metadata
- Purpose: Setup and verification guide for smartwatch OAuth, diagnostics, and sync behavior.
- Audience: Developers, QA engineers, support maintainers.
- Last Verified: 2026-03-27
- Verified Against: `feature_routes/smartwatch_routes.py`, `controllers/smartwatch_controller.py`, `services/smartwatch_service.py`, `jobs/scheduler.py`.
- Source of Truth: Route/controller/service behavior in code.

## Task-Based Navigation
- I need environment keys: [Environment Configuration](#environment-configuration)
- I need OAuth callback setup: [OAuth Provider Setup](#oauth-provider-setup-google-fit)
- I need runtime behavior details: [Runtime and Scheduler Behavior](#runtime-and-scheduler-behavior)
- I need debug guidance: [Troubleshooting Matrix](#troubleshooting-matrix)

## Environment Configuration
Copy template and configure smartwatch values:

```powershell
copy ..\.env.example ..\.env
```

Required keys:
```env
PHMS_BASE_URL=http://127.0.0.1:5000
SMARTWATCH_OAUTH_CALLBACK_PATH=/smartwatch/callback
GOOGLE_FIT_CLIENT_ID=<google-client-id>
GOOGLE_FIT_CLIENT_SECRET=<google-client-secret>

RATELIMIT_SMARTWATCH_AUTH=5 per minute
RATELIMIT_SMARTWATCH_MODIFY=10 per hour
RATELIMIT_SMARTWATCH_SYNC=10 per hour
RATELIMIT_SMARTWATCH_STATUS=30 per minute
```

## OAuth Provider Setup (Google Fit)
Provider callback URL must match:
```text
<PHMS_BASE_URL><SMARTWATCH_OAUTH_CALLBACK_PATH>
```
Example:
```text
http://127.0.0.1:5000/smartwatch/callback
```

## Database Migrations
After pulling schema changes:
```powershell
cd PHMS
.\venv\Scripts\Activate.ps1
flask db upgrade
```

## Runtime and Scheduler Behavior
Verified behavior:
- Importing app modules does not auto-start scheduler.
- Runtime bootstrap determines whether scheduler starts in current process.
- Smartwatch periodic sync job runs from scheduler configuration.
- Sync job processes connected accounts and records per-account failures without stopping entire job.

Important:
- For multi-worker deployments, scheduler should run in one dedicated process. (Operational pattern; see deployment docs if needed.)

## Local Verification Steps
1. Start app (`python start.py` or `python app.py`).
2. Open `/smartwatch`.
3. Execute connect flow and verify callback return state.
4. Trigger `sync-now` via UI/API.
5. Check `GET /smartwatch/status/google_fit`.
6. Run diagnostics endpoint and inspect metric availability.
7. Run smartwatch tests:
```powershell
python -m pytest tests/smartwatch -q
```

## Expected Data Behavior
- PHMS can ingest only metric families available through provider data.
- Sync pipeline supports deduplication and incomplete snapshot handling.
- Ingestion behavior for incomplete snapshots is enforced by health ingestion rules.

## Troubleshooting Matrix
1. Symptom: OAuth callback fails.
- Check exact callback URL match and state handling.

2. Symptom: Sync returns little/no data.
- Verify provider account has metric history for requested window.
- Run pre-sync diagnostics endpoint.

3. Symptom: Scheduler sync not running.
- Verify scheduler enabled in current runtime mode.
- Verify connected smartwatch account exists.

## Needs Verification
- Vendor-specific watch app behavior can change over time; always verify metric availability with current provider app version.

## See Also
- [API_REFERENCE.md](API_REFERENCE.md)
- [ENVIRONMENT_CONFIGURATION.md](ENVIRONMENT_CONFIGURATION.md)
- [TESTING_GUIDE.md](TESTING_GUIDE.md)
- [README.md](../../README.md)
