def test_core_feature_endpoints_registered(app):
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}

    expected = {
        'home',
        'register',
        'login',
        'logout',
        'forgot_password',
        'reset_password',
        'change_password',
        'dashboard',
        'profile',
        'update_profile',
        'health_page',
        'add_health',
        'delete_health',
        'medication_page',
        'add_medication',
        'delete_medication',
        'add_medicine_master',
        'notifications_page',
        'get_notifications',
        'get_notification_count',
        'mark_notification_read',
        'mark_all_notifications_read',
        'mark_medication_taken',
        'mark_medication_missed',
        'get_medication_logs',
        'update_medication_log_status',
        'get_user_medication_status',
        'create_medication_logs_manual',
        'manually_send_notifications',
        'manually_check_grace_period',
        'manually_check_consecutive_missed',
    }

    missing = sorted(expected - endpoints)
    assert not missing, f'Missing route endpoints: {missing}'


def test_reports_blueprint_registered(app):
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    assert 'reports.reports_home' in endpoints
