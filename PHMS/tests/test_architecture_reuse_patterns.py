import inspect


def test_scheduler_config_uses_jobs_layer_callbacks():
    from jobs.scheduler import SCHEDULER_CONFIG

    jobs = SCHEDULER_CONFIG.get('JOBS', [])
    assert jobs, 'Expected scheduler jobs to be configured'

    callback_paths = [job.get('func', '') for job in jobs]
    assert all(path.startswith('jobs.') for path in callback_paths)


def test_medication_tasks_remain_thin_service_delegates():
    import jobs.medication_tasks as medication_tasks

    source = inspect.getsource(medication_tasks)

    assert 'from services.medication_log_service import MedicationLogManager' in source
    assert 'from models' not in source
    assert 'from config import db' not in source


def test_reports_routes_delegate_to_report_service():
    import reports.routes.report_routes as report_routes

    source = inspect.getsource(report_routes)

    assert 'from reports.services.report_service import ReportDateRange, build_report_for_range' in source
    assert 'from models import' not in source


def test_medication_log_service_keeps_compatibility_facade_exports():
    import services.medication_log_service as facade

    expected_exports = {
        'MedicationLogManager',
        'update_medication_log_status',
        'get_user_medication_status',
        'create_medication_logs_manual',
        'manually_send_notifications',
        'manually_check_grace_period',
        'manually_check_consecutive_missed',
        'mark_medication_taken',
        'mark_medication_missed',
        'get_medication_logs',
    }

    missing = sorted(name for name in expected_exports if not hasattr(facade, name))
    assert not missing, f'Missing facade exports: {missing}'


def test_medication_log_status_endpoints_use_repository_queries():
    import services.medication_log.status_endpoints as status_endpoints

    source = inspect.getsource(status_endpoints)

    assert 'MedicationLog.query' not in source
    assert 'from models import' not in source
    assert 'from repositories.medication_log_repository import MedicationLogRepository' in source


def test_profile_service_uses_repositories_for_cross_domain_queries():
    import services.profile_service as profile_service

    source = inspect.getsource(profile_service)

    assert 'HealthData.query' not in source
    assert 'Medication.query' not in source
    assert 'Alert.query' not in source
    assert 'HealthRepository' in source
    assert 'MedicationRepository' in source
    assert 'AlertRepository' in source
