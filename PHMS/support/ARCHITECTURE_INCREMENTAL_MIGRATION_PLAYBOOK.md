# Architecture Incremental Migration Playbook

## Document Metadata
- Purpose: Practical migration patterns for incremental refactoring without breaking stable runtime behavior.
- Audience: Maintainers and contributors performing architecture cleanup.
- Last Verified: 2026-03-27
- Verified Against: Current feature routes, controllers, services, repositories, jobs.
- Source of Truth: Existing layered implementation patterns already in repository.

## Task-Based Navigation
- I need layering rules: [Layering Standards](#layering-standards)
- I need incremental migration sequence: [Migration Sequence Per Domain](#migration-sequence-per-domain)
- I need done criteria: [Done Criteria](#done-criteria)

## Why This Exists
PHMS already contains reusable architecture slices. The safest migration path is to copy proven patterns, not rewrite entire domains.

## Reusable Patterns in Current Codebase
1. Feature route composition via `feature_routes/*` and central `routes.py` registration.
2. Controller transport boundary that parses requests and delegates to services.
3. Service orchestration layer with repository-backed persistence.
4. Background jobs as thin callbacks in `jobs/*` delegating into services.
5. Compatibility facades for safe module split transitions:
   - `services/medication_log_service.py`
   - `scheduler_config.py`

## Layering Standards
### Routes
- Keep URL wiring only.
- Do not add business logic.

### Controllers
- Parse transport concerns (JSON/query/path/session).
- Normalize input and return HTTP response shape.
- Delegate business logic to services.

### Services
- Own workflow decisions and domain rules.
- Coordinate repositories and side effects.
- Avoid direct HTTP coupling.

### Repositories
- Own query composition and persistence helpers.
- Keep query intent explicit and reusable.

### Jobs
- Keep callbacks thin and idempotent-oriented.
- Delegate work to service layer.

## Migration Sequence Per Domain
1. Freeze endpoint contract (no URL/name breakage during migration).
2. Move business logic out of controllers into services.
3. Move reusable queries into repositories.
4. Add/expand schema validation at service boundary.
5. Add compatibility facades if import paths change.
6. Add or update tests (route wiring, transport validation, service behavior).
7. Remove dead code only after migration tests pass.

## Risk Controls
- Preserve existing route aliases during transition.
- Keep compatibility modules until all call sites are migrated.
- Prefer small PRs per domain boundary.
- Validate startup behavior to avoid accidental background-service starts on import.

## Done Criteria
A migrated domain is considered complete when:
1. Route file contains routing only.
2. Controller contains transport logic only.
3. Service contains business logic.
4. Repository contains persistence/query logic.
5. Existing tests pass and migration-specific tests exist.
6. Legacy compatibility exports remain only where still required.

## See Also
- [MEDICATION_LOG_SYSTEM_COMPREHENSIVE_GUIDE.md](MEDICATION_LOG_SYSTEM_COMPREHENSIVE_GUIDE.md)
- [TESTING_GUIDE.md](TESTING_GUIDE.md)
- [README.md](../../README.md)
