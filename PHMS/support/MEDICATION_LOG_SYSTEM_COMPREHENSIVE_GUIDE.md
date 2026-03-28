# PHMS Medication Log and Notification Guide

## Document Metadata
- Purpose: Runtime-accurate guide for medication log lifecycle, reminders, grace handling, and related admin endpoints.
- Audience: Backend developers, QA engineers, maintainers.
- Last Verified: 2026-03-27
- Verified Against: `PHMS/services/medication_log/*`, `PHMS/controllers/medication_log_controller.py`, `PHMS/jobs/scheduler.py`, `PHMS/feature_routes/medication_log_routes.py`, `PHMS/static/js/notifications.js`.
- Source of Truth: Medication log service/repository/scheduler code.

## Task-Based Navigation
- I need lifecycle behavior: [Lifecycle Summary](#lifecycle-summary)
- I need scheduler jobs: [Scheduler Jobs](#scheduler-jobs)
- I need status transition rules: [Status Transition Rules](#status-transition-rules)
- I need API endpoints: [Endpoint Surface](#endpoint-surface)

## Scope
This document covers medication log generation, notification dispatch, status transitions, grace period checks, and email side effects.

## Architecture Snapshot
Layered flow:
1. Routes in `feature_routes/medication_log_routes.py`
2. Controller transport in `controllers/medication_log_controller.py`
3. Service logic in `services/medication_log/status_endpoints.py` and `services/medication_log/*`
4. Persistence via `repositories/medication_log_repository.py`

Compatibility facade:
- `services/medication_log_service.py` re-exports medication-log manager and endpoint helpers.

## Lifecycle Summary
1. Daily logs are created for active medications using configured frequency schedules.
2. Reminder notifications are evaluated every minute around scheduled times.
3. Pending logs beyond grace are marked missed by background checks.
4. Startup catch-up marks overdue pending logs as skipped.
5. Manual status updates are validated against schedule/grace constraints.

## Scheduler Jobs
Configured by `jobs/scheduler.py`:
- `create_daily_logs` at 00:00
- `schedule_notifications` every 1 minute
- `check_grace_period` every 1 minute

Additional periodic smartwatch sync job is configured separately and out of this guide’s core scope.

## Grace Period Rules
Grace period is dynamic:
- `grace = min(30 minutes, minimum gap between doses for medication frequency)`

Consequences:
- High-frequency schedules may have grace below 30 minutes.
- Mark-as-taken/missed endpoints enforce schedule/grace checks.

## Status Transition Rules
Supported statuses:
- `pending`
- `taken`
- `missed`
- `skipped`

Key runtime rules:
- Cannot mark taken/missed before scheduled time.
- If grace expired, user-facing mark operations return guidance/error rather than force-taking.
- Background grace check marks overdue pending logs missed.
- Startup catch-up marks historical overdue pending logs skipped.

## Notification and Email Behavior
Reminder creation:
- Notification scheduler evaluates pending logs near scheduled time window.
- Duplicate reminder creation is guarded.

Email workflows:
- Critical medication reminder emails can be sent at notification time.
- Critical missed and consecutive-missed email workflows exist.
- Email send retries are implemented; fallback in-app alert is created on final delivery failure.

Consecutive missed behavior:
- Deprecated manual/dedicated check function remains for backward compatibility.
- Active consecutive-missed handling is integrated into missed-flow logic.

## Endpoint Surface
User endpoints:
- `PUT /medication-log/<log_id>/taken`
- `PUT /medication-log/<log_id>/missed`
- `PUT /medication-log/status/<log_id>`
- `GET /medication-log/status`
- `GET /medication-log/api`

Admin endpoints:
- `POST /medication-log/create-daily`
- `POST /medication-log/send-notifications`
- `POST /medication-log/check-grace-period`
- `POST /medication-log/check-consecutive-missed` (deprecated passthrough)

See full request/response details in [API_REFERENCE.md](API_REFERENCE.md).

## UI Interaction Note
`PHMS/static/js/notifications.js` polls medication button state every 5 seconds (`setInterval(..., 5000)`).

## Known Compatibility Notes
- `scheduler_config.py` is a compatibility wrapper over `jobs/scheduler.py`.
- `services/medication_log_service.py` is a compatibility facade over the modular medication-log package.

## Needs Verification
- If frequency parsing rules in `utils/medication_schedule.py` change, re-verify grace and consecutive-gap examples.

## See Also
- [API_REFERENCE.md](API_REFERENCE.md)
- [TESTING_GUIDE.md](TESTING_GUIDE.md)
- [README.md](../../README.md)
- [ARCHITECTURE_INCREMENTAL_MIGRATION_PLAYBOOK.md](ARCHITECTURE_INCREMENTAL_MIGRATION_PLAYBOOK.md)
