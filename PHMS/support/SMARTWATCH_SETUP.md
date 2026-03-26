# Smartwatch OAuth and Scheduler Setup

This guide covers environment setup, OAuth provider configuration, migration steps, scheduler behavior, and local verification for smartwatch integration.

It also includes Fire-Boltt + Da Fit notes, because that combination commonly syncs only partial metrics to Google Fit.

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

If your app runs behind HTTPS/proxy in production, use your public HTTPS base URL for PHMS_BASE_URL.

## 3. Database Migrations

Run migrations before starting app after pulling schema changes:

```powershell
cd PHMS
.\venv\Scripts\Activate.ps1
flask db upgrade
```

This applies smartwatch account/sync tables and health ingestion dedupe fields.

## 4. Runtime and Scheduler Behavior

Runtime wiring is explicit and aligned with app.py:

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

Default behavior:

- Periodic smartwatch sync runs every 6 hours.
- The job syncs only accounts with connection_status=connected.
- If no connected account exists, scheduler exits cleanly for that run.

## 5. Local Verification

1. Start app:

```powershell
python start.py
```

1. Open Smartwatch page:

```text
http://127.0.0.1:5000/smartwatch
```

1. Validate OAuth flow:

- Click Connect
- Provider consent redirects to callback
- Callback returns to Smartwatch page with status message

1. Validate sync/status APIs:

- Trigger Sync Now in UI
- Check GET /smartwatch/status/google_fit

1. Validate pre-sync diagnostics:

- Click Pre-sync Diagnostics
- Confirm metric_point_totals and non_zero_metric_families in response/logs

1. Validate tests:

```powershell
python -m pytest tests/smartwatch -q
```

Expected: smartwatch suite passes.

## 6. Fire-Boltt + Da Fit + Google Fit Checklist

If testing with Fire-Boltt via Da Fit, complete this checklist before backend debugging.

1. In Da Fit:

- Pair watch and confirm active sync.
- Enable Google Fit integration.
- Reconnect Google Fit from Da Fit if already linked (forces fresh grant).

1. In Android app permissions for Da Fit:

- Allow Physical Activity.
- Allow Sensors.
- Allow Location if required by your phone ROM/vendor.
- Disable battery optimization for Da Fit.
- Allow background activity/autostart.

1. In Google Fit app:

- Verify timeline contains data for the same test window.
- Verify which families actually have points (steps, heart rate, sleep, etc.).

Important:

- PHMS can only read what Google Fit stores.
- If Google Fit has points=0 for a family, PHMS cannot fabricate that metric.

## 7. Expected Device Behavior

Different device ecosystems sync different families to Google Fit.

- Commonly available: steps.
- Sometimes available: heart rate, sleep.
- Often missing for many watches: temperature, blood pressure, glucose.

Current backend behavior (by design):

- Adapter fetches all required families with adaptive windows.
- Adapter merges whatever is available and returns partial payload if needed.
- Ingestion layer enforces strict completeness for smartwatch payloads.

## 8. Troubleshooting Matrix

Use this matrix to quickly isolate the issue source.

1. Symptom: Diagnostics show dataset refs but points=0 for non-step families.

- Likely cause: Source app/device is not exporting those families into Google Fit.
- Action: Fix Da Fit permissions/sync settings and verify Google Fit timeline first.

1. Symptom: Only steps ingested attempt, then payload skipped as incomplete.

- Likely cause: Strict smartwatch ingestion requires all required fields.
- Action: Confirm non-step families exist in Google Fit or use manual health entry for missing fields.

1. Symptom: Sync always empty immediately after prior sync.

- Likely cause: Stored incremental boundary too narrow.
- Action: Current service has fallback adaptive lookback retry; review logs for "Empty incremental sync ... retrying once".

1. Symptom: Scheduler not syncing connected accounts.

- Likely cause: Scheduler process not enabled in runtime.
- Action: Set ENABLE_SCHEDULER=1 in dedicated scheduler process.

## 9. Recommended Log Lines

When validating a run, confirm these signals in logs:

- Fetch attempt line: requested_data_types, metrics_found, metrics_missing.
- Dataset refs line: Google Fit refs with points count.
- Final merge line: final merged metrics and final missing list.
- Sync summary line: fetched, ingested, deduplicated, incomplete, failed.
