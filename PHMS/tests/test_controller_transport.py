from types import SimpleNamespace


def test_health_add_rejects_non_json_payload(app):
    from controllers import health_controller

    with app.test_request_context('/add-health', method='POST', data='plain', content_type='text/plain'):
        response, status_code = health_controller.add_health.__wrapped__()

    assert status_code == 415
    assert response.get_json()['success'] is False


def test_medication_add_coerces_is_critical_flag(app, monkeypatch):
    from controllers import medication_controller

    captured = {}

    def fake_create_medication(user_id, payload):
        captured['user_id'] = user_id
        captured['payload'] = payload
        return {'success': True, 'status_code': 201}

    monkeypatch.setattr(medication_controller, 'create_medication', fake_create_medication)
    monkeypatch.setattr(medication_controller, 'current_user', SimpleNamespace(user_id=77))

    with app.test_request_context(
        '/add-medication',
        method='POST',
        json={
            'medicine_name': 'Aspirin',
            'dosage': '10mg',
            'frequency': 1,
            'start_date': '2030-01-01',
            'end_date': '2030-01-02',
            'is_critical': 'yes',
        },
    ):
        _, status_code = medication_controller.add_medication.__wrapped__()

    assert status_code == 201
    assert captured['user_id'] == 77
    assert captured['payload']['is_critical'] is True


def test_notifications_api_limit_is_clamped(app, monkeypatch):
    from controllers import notifications_controller

    captured = {}

    def fake_fetch_notifications(user_id, limit):
        captured['user_id'] = user_id
        captured['limit'] = limit
        return {'success': True, 'notifications': [], 'count': 0, 'status_code': 200}

    monkeypatch.setattr(notifications_controller, 'fetch_notifications', fake_fetch_notifications)
    monkeypatch.setattr(notifications_controller, 'current_user', SimpleNamespace(user_id=11))

    with app.test_request_context('/notifications/api?limit=9999', method='GET'):
        _, status_code = notifications_controller.get_notifications.__wrapped__()

    assert status_code == 200
    assert captured['user_id'] == 11
    assert captured['limit'] == 100
