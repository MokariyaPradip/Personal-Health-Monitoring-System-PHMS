# PHMS REST API Reference

## Document Metadata
- Purpose: Authoritative HTTP API contract for currently registered PHMS endpoints.
- Audience: Backend developers, frontend developers, QA engineers.
- Last Verified: 2026-03-27
- Verified Against: `PHMS/routes.py`, `PHMS/feature_routes/*`, `PHMS/controllers/*`, `PHMS/services/*`.
- Source of Truth: Route registration and controller/service return behavior in code.

## Task-Based Navigation
- I need auth/session endpoints: [Public and Session Endpoints](#public-and-session-endpoints)
- I need health/medication contracts: [Health Endpoints](#health-endpoints), [Medication Endpoints](#medication-endpoints), [Medication Log Endpoints](#medication-log-endpoints)
- I need smartwatch APIs: [Smartwatch Endpoints](#smartwatch-endpoints)
- I need report exports: [Report Endpoints](#report-endpoints)
- I need environment variables for these routes: see [ENVIRONMENT_CONFIGURATION.md](ENVIRONMENT_CONFIGURATION.md)
- I need testing commands for these APIs: see [TESTING_GUIDE.md](TESTING_GUIDE.md)

## Base URL
- Local development: `http://127.0.0.1:5000`
- Runtime base URL for integrations: controlled by `PHMS_BASE_URL`

## Authentication and Session Contract

| Mode | How it works | Applies to |
|---|---|---|
| Public | No existing session required | Register/Login/Forgot/Reset routes |
| Session-required | Flask-Login session cookie required | Most application routes |
| Admin-required | Authenticated + `is_admin=True` | Manual medication-log admin actions |

Notes:
- PHMS primarily uses session auth (cookie-based), not bearer tokens.
- CSRF and cookie behavior are configured in `config.py` and enforced by app middleware/extensions.

## Request and Response Conventions

### Content Type
- JSON endpoints expect `Content-Type: application/json` for JSON bodies.
- Some auth routes accept form payloads for compatibility (`forgot-password`, `reset-password`).

### Success Envelope (common pattern)
```json
{
  "success": true,
  "message": "Human-readable status"
}
```

### Error Envelope (common pattern)
```json
{
  "success": false,
  "message": "Error summary"
}
```

Notes:
- Most controllers pop internal `status_code` before returning the HTTP response.
- Some controlled auth failures intentionally still return HTTP `200` with `success: false` (for example invalid login credentials).

## HTTP Status Code Reference

| Code | Meaning in PHMS |
|---|---|
| 200 | Success or controlled negative auth outcome |
| 201 | Resource/flow created (for example OAuth authorization URL generation) |
| 400 | Validation failure or invalid transition |
| 401 | Provider auth exchange failure (provider-dependent) |
| 403 | Forbidden (admin required / disconnected account / policy) |
| 404 | Resource/account/provider not found |
| 409 | Duplicate/conflict |
| 415 | Invalid or missing JSON content type on strict JSON routes |
| 429 | Rate limit exceeded |
| 500 | Unexpected server error |

## Public and Session Endpoints

### Root
| Endpoint | Method | Auth | Contract |
|---|---|---|---|
| `/` | GET | Public | Redirects to `/login` |

### Auth
| Endpoint | Method(s) | Auth | Key Request Shape | Key Response Shape |
|---|---|---|---|---|
| `/register` | GET, POST | Public | `username,email,password` required; optional profile fields | `success,message` |
| `/login` | GET, POST | Public | `email,password` | `success,message` |
| `/logout` | POST | Session | none | Redirect to `/login` |
| `/forgot-password` (+ `/forgotPassword`) | GET, POST | Public | `email` | `success,message` |
| `/reset-password` (+ `/resetPassword`) | GET, POST | Public | step-based payload: `email`, then `otp`, then `password+confirm_password` | `success,message,step?` |
| `/change-password` (+ `/changePassword`) | PUT | Session | `current_password,new_password,confirm_password` | `success,message` |

Rate-limited auth endpoints:
- `/register` -> `RATELIMIT_REGISTRATION`
- `/login` -> `RATELIMIT_AUTH_ATTEMPTS`
- `/forgot-password` and `/reset-password` -> `RATELIMIT_PASSWORD_RESET`
- `/change-password` -> `RATELIMIT_CHANGE_PASSWORD`

## Dashboard and Profile Endpoints

| Endpoint | Method | Auth | Key Request/Params | Success Response |
|---|---|---|---|---|
| `/dashboard` | GET | Session | none | HTML dashboard page |
| `/profile` | GET | Session | none | HTML profile page |
| `/update-profile` (+ `/updateProfile`) | PUT | Session | JSON fields: `username,age,gender,height,weight` | `success,message,bmi` |

## Health Endpoints

| Endpoint | Method | Auth | Key Request/Params | Success Response |
|---|---|---|---|---|
| `/health` | GET | Session | query: `page`, `source=all|manual|google_fit` | HTML health page |
| `/add-health` (+ `/add_health`) | POST | Session | JSON object with health metrics | `success,message` plus ingestion metadata fields |
| `/delete-health/<entry_id>` (+ aliases) | DELETE | Session | path: `entry_id` | `success,message` |

Validation ranges (from schema):
- heart_rate: 30..220
- temperature: 35..42
- steps: 0..60000
- sleep_hours: 0..24
- blood_pressure: 40..250
- sugar: 40..600

## Medication Endpoints

| Endpoint | Method | Auth | Key Request/Params | Success Response |
|---|---|---|---|---|
| `/medication` | GET | Session | query: `query`, `view_all` | HTML medication page |
| `/add-medication` (+ `/addMedication`) | POST | Session | JSON: `medicine_name,dosage,frequency,start_date,end_date,is_critical` | `success,message,logs_created` |
| `/delete-medication/<id>` (+ alias) | DELETE | Session | path: `id` | `success,message` |
| `/add-medicine` (+ `/addMedicine`) | POST | Session | JSON: `medicine_name,purpose` (required), optional `medicine_type,remark` | `success,message` |

## Medication Log Endpoints

| Endpoint | Method | Auth | Key Request/Params | Success Response |
|---|---|---|---|---|
| `/medication-log/<log_id>/taken` | PUT | Session | path: `log_id` | `success,message` |
| `/medication-log/<log_id>/missed` | PUT | Session | path: `log_id` | `success,message,email_notification_failed?` |
| `/medication-log/api` | GET | Session | query: `days` (default 7), `status` | `success,count,logs[]` |
| `/medication-log/status/<log_id>` | PUT | Session | JSON: `status=taken|missed|pending|skipped` | `success,message` |
| `/medication-log/status` | GET | Session | none | `success,data` |

Admin-only operational endpoints:
| Endpoint | Method | Auth |
|---|---|---|
| `/medication-log/create-daily` | POST | Admin |
| `/medication-log/send-notifications` | POST | Admin |
| `/medication-log/check-grace-period` | POST | Admin |
| `/medication-log/check-consecutive-missed` | POST | Admin (deprecated passthrough behavior) |

## Notification Endpoints

| Endpoint | Method | Auth | Key Request/Params | Success Response |
|---|---|---|---|---|
| `/notifications` | GET | Session | query: `tab=all|health|medication|medication-log` | HTML notifications page |
| `/notifications/api` | GET | Session | query: `limit` (1..100) | `success,count,notifications[]` |
| `/notifications/count` | GET | Session | none | `success,count` |
| `/notifications/<alert_id>/read` | PUT | Session | path: `alert_id` | `success,message` |
| `/notifications/mark-all-read` | PUT | Session | none | `success,message,updated_count,...` |

## Report Endpoints

| Endpoint | Method | Auth | Key Request/Params | Success Response |
|---|---|---|---|---|
| `/reports` | GET | Session | optional `feature`, `format` | HTML/JSON/CSV based on format negotiation |
| `/reports/weekly` | GET | Session | optional `feature`, `format` | HTML/JSON/CSV |
| `/reports/monthly` | GET | Session | optional `feature`, `format` | HTML/JSON/CSV |
| `/reports/yearly` | GET | Session | optional `feature`, `format` | HTML/JSON/CSV |
| `/reports/custom` | GET | Session | `start_date,end_date` required; optional `feature`, `format` | HTML/JSON/CSV or validation error |
| `/reports/<report_type>/pdf` | GET | Session | `report_type` in weekly/monthly/yearly/custom; dates for custom | PDF download |

## Smartwatch Endpoints

| Endpoint | Method | Auth | Key Request/Params | Success Response |
|---|---|---|---|---|
| `/smartwatch` and `/smartwatch/integration` | GET | Session | optional `provider` | HTML smartwatch page |
| `/smartwatch/authorize/<provider>` | GET | Session | path: provider | `success,authorization_url,provider,message` |
| `/smartwatch/callback` | GET | Session | query: `code,state,error?` | redirect with status message |
| `/smartwatch/disconnect/<provider>` | POST | Session | path: provider | `success,message` |
| `/smartwatch/sync-now/<provider>` | POST | Session | optional JSON: `cursor,since` | `success,sync_result` |
| `/smartwatch/pre-sync-diagnostics/<provider>` | GET | Session | optional query: `cursor,since` | `success,...diagnostics` |
| `/smartwatch/status/<provider>` | GET | Session | path: provider | `success,account,sync_state` |

Rate-limited smartwatch routes:
- auth/callback: `RATELIMIT_SMARTWATCH_AUTH`
- disconnect: `RATELIMIT_SMARTWATCH_MODIFY`
- sync/diagnostics: `RATELIMIT_SMARTWATCH_SYNC`
- status/page: `RATELIMIT_SMARTWATCH_STATUS`

## Legacy Compatibility Aliases

Maintained aliases include:
- `/forgotPassword`, `/resetPassword`, `/changePassword`
- `/add_health`, `/delete_health/<entry_id>`, `/deleteHealth/<entry_id>`
- `/addMedication`, `/deleteMedication/<id>`, `/addMedicine`
- `/updateProfile`

## Needs Verification

The following are implementation-adjacent and should be re-verified after major auth/security middleware changes:
- Exact CSRF behavior for each JSON route by HTTP method and frontend transport path.
- Any custom reverse-proxy/session-cookie behavior not visible at route/controller layer.

## See Also
- [README.md](../../README.md)
- [TESTING_GUIDE.md](TESTING_GUIDE.md)
- [ENVIRONMENT_CONFIGURATION.md](ENVIRONMENT_CONFIGURATION.md)
- [SMARTWATCH_SETUP.md](SMARTWATCH_SETUP.md)
- [MEDICATION_LOG_SYSTEM_COMPREHENSIVE_GUIDE.md](MEDICATION_LOG_SYSTEM_COMPREHENSIVE_GUIDE.md)
