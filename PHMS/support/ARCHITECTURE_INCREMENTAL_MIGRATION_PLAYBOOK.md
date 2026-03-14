# Architecture Incremental Migration Playbook

This playbook captures proven patterns already present in PHMS and defines how to reuse them for low-risk, incremental migration.

## Why This Exists

PHMS already has working architecture slices that match the target layering model:

1. Route -> service split in reports:
   1. `reports/routes/report_routes.py`
   2. `reports/services/report_service.py`
2. Scheduler orchestration -> job callbacks split:
   1. `jobs/scheduler.py`
   2. `jobs/medication_tasks.py`
3. Modular medication-log domain with compatibility facade:
   1. `services/medication_log/manager.py`
   2. `services/medication_log_service.py`

The goal is to reuse these patterns instead of rewrite-heavy refactors.

## Reusable Patterns

### 1. Feature Route Composition

Pattern:
1. Keep `feature_routes/*_routes.py` focused on URL wiring only.
2. Delegate all behavior to controllers.
3. Keep central registration as a thin composition layer.

Use this for any new feature endpoint set.

### 2. Controller as Transport Boundary

Pattern:
1. Parse request input (JSON/content type/query args).
2. Normalize transport-specific fields.
3. Delegate business logic to service layer.
4. Convert service result to HTTP response.

Do not place ORM queries in controllers.

### 3. Service as Application Logic Layer

Pattern:
1. Hold business rules, orchestrations, workflow decisions.
2. Consume schemas for input validation.
3. Delegate data access to repositories.

Do not embed HTTP request/response concerns in services.

### 4. Repository as Data Access Layer

Pattern:
1. Keep SQLAlchemy query blocks in repositories.
2. Expose explicit query methods for service use.
3. Keep transaction ownership in service where workflows span multiple writes.

### 5. Background Jobs as Thin Callbacks

Pattern:
1. Keep `jobs/*.py` callbacks tiny.
2. Delegate work to service methods.
3. Keep scheduler setup in `jobs/scheduler.py`.

Do not place business logic in scheduler configuration.

### 6. Compatibility Facades for Safe Refactor

Pattern:
1. When splitting large modules, preserve import contracts via a facade module.
2. Re-export stable symbols from the new package structure.
3. Migrate call sites gradually.

This enables non-breaking incremental migration.

## Incremental Migration Steps (Per Domain)

1. Add/expand service methods first while keeping controller signatures unchanged.
2. Move ORM query blocks into repository methods.
3. Introduce schema validation for service inputs.
4. Add compatibility facade exports if module paths change.
5. Keep route endpoint names stable; add aliases only when needed.
6. Add focused tests for route registration, transport behavior, and service validation.
7. Remove legacy paths only after tests and consumers are migrated.

## Done Criteria

A migrated domain is complete when:

1. Controllers contain only transport logic.
2. Services contain business logic and orchestration.
3. Repositories own query logic.
4. Background jobs delegate to services.
5. Legacy imports (if any) are preserved by facades during transition.
6. Tests verify route wiring and service validation behavior.
