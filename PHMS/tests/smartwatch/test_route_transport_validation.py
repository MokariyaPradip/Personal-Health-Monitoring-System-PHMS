from types import SimpleNamespace

from controllers import smartwatch_controller


def test_parse_json_object_payload_rejects_non_json(app):
    with app.test_request_context('/smartwatch/sync-now/google_fit', method='POST', data='plain', content_type='text/plain'):
        payload, error = smartwatch_controller._parse_json_object_payload()

    assert payload is None
    assert error is not None
    response, status_code = error
    assert status_code == 415
    assert response.get_json()['success'] is False


def test_parse_json_object_payload_rejects_invalid_json(app):
    with app.test_request_context(
        '/smartwatch/sync-now/google_fit',
        method='POST',
        data='{invalid',
        content_type='application/json',
    ):
        payload, error = smartwatch_controller._parse_json_object_payload()

    assert payload is None
    response, status_code = error
    assert status_code == 400
    assert response.get_json()['message'] == 'Invalid JSON payload'


def test_parse_json_object_payload_rejects_json_array(app):
    with app.test_request_context(
        '/smartwatch/sync-now/google_fit',
        method='POST',
        json=['not', 'an', 'object'],
    ):
        payload, error = smartwatch_controller._parse_json_object_payload()

    assert payload is None
    response, status_code = error
    assert status_code == 400
    assert response.get_json()['message'] == 'JSON body must be an object'


def test_sync_now_transports_cursor_and_since_to_service(app, monkeypatch):
    captured = {}

    def fake_trigger_sync(user_id, provider, cursor=None, since=None):
        captured['user_id'] = user_id
        captured['provider'] = provider
        captured['cursor'] = cursor
        captured['since'] = since
        return {
            'success': True,
            'message': 'ok',
            'status_code': 200,
            'sync_result': {'fetched_count': 0, 'ingested_count': 0, 'deduplicated_count': 0, 'failed_count': 0, 'errors': []},
        }

    monkeypatch.setattr(smartwatch_controller.smartwatch_service, 'trigger_sync', fake_trigger_sync)
    monkeypatch.setattr(smartwatch_controller, 'current_user', SimpleNamespace(user_id=123))

    with app.test_request_context(
        '/smartwatch/sync-now/google_fit',
        method='POST',
        json={'cursor': 'cursor-1', 'since': '2026-03-20T00:00:00Z'},
    ):
        response, status_code = smartwatch_controller.sync_now.__wrapped__('google_fit')

    assert status_code == 200
    assert response.get_json()['success'] is True
    assert captured == {
        'user_id': 123,
        'provider': 'google_fit',
        'cursor': 'cursor-1',
        'since': '2026-03-20T00:00:00Z',
    }


def test_callback_redirects_to_error_when_code_missing(app, monkeypatch):
    monkeypatch.setattr(smartwatch_controller, 'current_user', SimpleNamespace(user_id=22))

    with app.test_request_context('/smartwatch/callback', method='GET'):
        response = smartwatch_controller.callback.__wrapped__()

    assert response.status_code == 302
    assert '/smartwatch/integration?' in response.location
    assert 'status=error' in response.location
