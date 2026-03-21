# PHMS Test Execution Guide

This file explains how to run tests in this project.

## 1) Run all tests (recommended)

From project root:

c:/Users/Admin/Desktop/Sem-06/2_SDP/project/PHMS/venv/Scripts/python.exe -m pytest -q

## 2) Run all tests with detailed output

From project root:

c:/Users/Admin/Desktop/Sem-06/2_SDP/project/PHMS/venv/Scripts/python.exe -m pytest -vv

## 3) Run one test file

From project root (example):

c:/Users/Admin/Desktop/Sem-06/2_SDP/project/PHMS/venv/Scripts/python.exe -m pytest PHMS/tests/test_medication_scheduler_integration.py -vv

## 4) Run one specific test case

From project root (example):

c:/Users/Admin/Desktop/Sem-06/2_SDP/project/PHMS/venv/Scripts/python.exe -m pytest PHMS/tests/test_secondary_integration_flows.py::test_auth_password_reset_locks_after_too_many_invalid_otp_attempts -vv

## 5) Notes

- pytest.ini is configured to discover tests under PHMS/tests.
- If rate-limit warnings appear in tests, they are expected in local in-memory test mode.
- Use the PHMS virtual environment interpreter shown above to avoid missing dependency issues.
