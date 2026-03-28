# PHMS Testing Guide

## Document Metadata
- Purpose: Canonical test execution and test-maintenance guide for PHMS.
- Audience: Developers, QA engineers, reviewers.
- Last Verified: 2026-03-27
- Verified Against: `pytest.ini`, `PHMS/tests/*`, current repository layout.
- Source of Truth: This document is canonical. `PHMS/tests/TESTING.md` is a pointer only.

## Task-Based Navigation
- I want to run all tests quickly: [Run All Tests](#run-all-tests)
- I want feature-targeted test runs: [Targeted Runs](#targeted-runs)
- I want to add/update tests: [Writing and Organizing Tests](#writing-and-organizing-tests)
- I want CI expectations: [CI and PR Expectations](#ci-and-pr-expectations)

## Test Stack and Discovery
- Framework: `pytest`
- Config: `pytest.ini`
- Discovery root: `PHMS/tests`
- Naming patterns:
  - `test_*.py`
  - `*_test.py`

Current key test files:
- `PHMS/tests/test_architecture_reuse_patterns.py`
- `PHMS/tests/test_controller_transport.py`
- `PHMS/tests/test_medication_scheduler_integration.py`
- `PHMS/tests/test_route_registration.py`
- `PHMS/tests/test_schema_validation_services.py`
- `PHMS/tests/test_secondary_integration_flows.py`
- `PHMS/tests/test_startup_behavior.py`
- `PHMS/tests/smartwatch/*`

## Environment Setup
From repository root:

```powershell
cd PHMS
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..
```

## Run All Tests
```powershell
python -m pytest -q
```

Verbose:
```powershell
python -m pytest -vv
```

Stop on first failure:
```powershell
python -m pytest -x -vv
```

## Targeted Runs
One file:
```powershell
python -m pytest PHMS/tests/test_route_registration.py -vv
```

One test case:
```powershell
python -m pytest PHMS/tests/test_secondary_integration_flows.py::test_auth_password_reset_locks_after_too_many_invalid_otp_attempts -vv
```

Smartwatch suite:
```powershell
python -m pytest PHMS/tests/smartwatch -q
```

## Writing and Organizing Tests
### Placement
- Put backend tests in `PHMS/tests/`
- Put smartwatch-specific tests in `PHMS/tests/smartwatch/`

### Naming
- File: `test_<feature>.py`
- Function: `test_<expected_behavior>`

### Test shape (recommended)
- Arrange: fixtures and data setup
- Act: invoke controller/service/route behavior
- Assert: status code, response payload, DB side effects

## Isolation and Reliability Guidance
- Prefer deterministic fixtures and explicit setup/teardown.
- Suppress SMTP side effects where needed: `MAIL_SUPPRESS_SEND=1`.
- Mock provider calls for smartwatch/OAuth behavior.
- Ensure scheduler behavior is tested via explicit bootstrap paths, not implicit imports.

## CI and PR Expectations
No CI workflow is currently committed under `.github/workflows`.

Recommended minimum pipeline:
1. Install dependencies
2. Run test suite
3. Fail on any failing test

Suggested commands:
```bash
python -m pip install --upgrade pip
pip install -r PHMS/requirements.txt
python -m pytest -q
```

PR quality expectations:
- New behavior should include tests.
- Bug fixes should include regression tests.
- Avoid coverage regression in auth, health ingestion, medication-log, and smartwatch flows.

## Troubleshooting
### Import errors
- Run tests from repository root.
- Confirm `pythonpath = PHMS` from `pytest.ini` is in effect.

### Missing dependencies
- Activate the intended venv.
- Reinstall dependencies from `PHMS/requirements.txt`.

### Flaky background-job behavior
- Verify tests are not unintentionally starting scheduler loops.
- Keep startup tests focused on explicit bootstrap behavior.

## See Also
- [README.md](../../README.md)
- [API_REFERENCE.md](API_REFERENCE.md)
- [ENVIRONMENT_CONFIGURATION.md](ENVIRONMENT_CONFIGURATION.md)
- [SMARTWATCH_SETUP.md](SMARTWATCH_SETUP.md)
