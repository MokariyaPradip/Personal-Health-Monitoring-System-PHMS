from types import SimpleNamespace

from controllers import smartwatch_controller
from services import smartwatch_service


def _fake_orchestrator_with_providers(provider_ids):
    class _FakeOrchestrator:
        def get_registered_provider_ids(self):
            return sorted(provider_ids)

    return _FakeOrchestrator()


def test_smartwatch_endpoints_registered(app):
    rules = {rule.endpoint: rule for rule in app.url_map.iter_rules()}

    expected_endpoints = {
        'smartwatch_page',
        'authorize',
        'callback',
        'disconnect',
        'sync_now',
        'status',
    }

    missing = sorted(expected_endpoints - set(rules.keys()))
    assert not missing, f'Missing smartwatch endpoints: {missing}'


def test_smartwatch_routes_have_expected_methods(app):
    routes_by_path = {rule.rule: rule.methods for rule in app.url_map.iter_rules()}

    assert 'GET' in routes_by_path['/smartwatch']
    assert 'GET' in routes_by_path['/smartwatch/integration']
    assert 'GET' in routes_by_path['/smartwatch/authorize/<provider>']
    assert 'GET' in routes_by_path['/smartwatch/callback']
    assert 'POST' in routes_by_path['/smartwatch/disconnect/<provider>']
    assert 'POST' in routes_by_path['/smartwatch/sync-now/<provider>']
    assert 'GET' in routes_by_path['/smartwatch/status/<provider>']


def test_integration_page_context_uses_requested_supported_provider(monkeypatch):
    monkeypatch.setattr(
        smartwatch_service,
        '_get_orchestrator',
        lambda: _fake_orchestrator_with_providers(['google_fit', 'fitbit']),
    )
    monkeypatch.setattr(
        smartwatch_service,
        'get_account_status',
        lambda user_id, provider: {
            'success': True,
            'account': {
                'provider': provider,
                'connection_status': 'disconnected',
                'last_error': None,
            },
            'sync_state': None,
        },
    )

    context = smartwatch_service.get_integration_page_context(10, provider='fitbit')

    assert context['provider'] == 'fitbit'
    assert context['provider_label'] == 'Fitbit'
    assert [p['id'] for p in context['supported_providers']] == ['fitbit', 'google_fit']


def test_integration_page_context_falls_back_to_first_supported_provider(monkeypatch):
    monkeypatch.setattr(
        smartwatch_service,
        '_get_orchestrator',
        lambda: _fake_orchestrator_with_providers(['google_fit', 'fitbit']),
    )
    monkeypatch.setattr(
        smartwatch_service,
        'get_account_status',
        lambda user_id, provider: {
            'success': False,
            'account': None,
            'sync_state': None,
        },
    )

    context = smartwatch_service.get_integration_page_context(10, provider='apple_health')

    assert context['provider'] == 'fitbit'
    assert context['provider_label'] == 'Fitbit'
    assert [p['label'] for p in context['supported_providers']] == ['Fitbit', 'Google Fit']


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
            'sync_result': {
                'fetched_count': 0,
                'ingested_count': 0,
                'deduplicated_count': 0,
                'incomplete_count': 0,
                'failed_count': 0,
                'errors': [],
            },
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


def test_sync_now_rejects_non_json_payload_when_body_present(app, monkeypatch):
    called = {'service_called': False}

    def fake_trigger_sync(user_id, provider, cursor=None, since=None):
        called['service_called'] = True
        return {'success': True, 'status_code': 200}

    monkeypatch.setattr(smartwatch_controller.smartwatch_service, 'trigger_sync', fake_trigger_sync)
    monkeypatch.setattr(smartwatch_controller, 'current_user', SimpleNamespace(user_id=123))

    with app.test_request_context(
        '/smartwatch/sync-now/google_fit',
        method='POST',
        data='plain',
        content_type='text/plain',
    ):
        response, status_code = smartwatch_controller.sync_now.__wrapped__('google_fit')

    assert status_code == 415
    assert response.get_json()['success'] is False
    assert called['service_called'] is False


def test_sync_now_rejects_malformed_json_when_body_present(app, monkeypatch):
    called = {'service_called': False}

    def fake_trigger_sync(user_id, provider, cursor=None, since=None):
        called['service_called'] = True
        return {'success': True, 'status_code': 200}

    monkeypatch.setattr(smartwatch_controller.smartwatch_service, 'trigger_sync', fake_trigger_sync)
    monkeypatch.setattr(smartwatch_controller, 'current_user', SimpleNamespace(user_id=123))

    with app.test_request_context(
        '/smartwatch/sync-now/google_fit',
        method='POST',
        data='{invalid',
        content_type='application/json',
    ):
        response, status_code = smartwatch_controller.sync_now.__wrapped__('google_fit')

    assert status_code == 400
    assert response.get_json()['success'] is False
    assert response.get_json()['message'] == 'Invalid JSON payload'
    assert called['service_called'] is False


def test_callback_redirects_to_error_when_code_missing(app, monkeypatch):
    monkeypatch.setattr(smartwatch_controller, 'current_user', SimpleNamespace(user_id=22))

    with app.test_request_context('/smartwatch/callback', method='GET'):
        from flask import session
        session['smartwatch_oauth_state'] = 'expected-state'
        response = smartwatch_controller.callback.__wrapped__()

    assert response.status_code == 302
    assert '/smartwatch/integration?' in response.location
    assert 'status=error' in response.location


def test_authorize_stores_oauth_state_in_session(app, monkeypatch):
    monkeypatch.setattr(smartwatch_controller, 'current_user', SimpleNamespace(user_id=101))

    def fake_get_authorization_url(user_id, provider):
        assert user_id == 101
        assert provider == 'google_fit'
        return {
            'success': True,
            'authorization_url': 'https://provider.example/auth?response_type=code&state=csrf-state-123',
            'provider': provider,
            'status_code': 201,
        }

    monkeypatch.setattr(
        smartwatch_controller.smartwatch_service,
        'get_authorization_url',
        fake_get_authorization_url,
    )

    with app.test_request_context('/smartwatch/authorize/google_fit', method='GET'):
        from flask import session

        response, status_code = smartwatch_controller.authorize.__wrapped__('google_fit')

        assert status_code == 201
        assert session.get('smartwatch_oauth_state') == 'csrf-state-123'
        assert session.get('smartwatch_oauth_provider') == 'google_fit'
        assert response.get_json()['success'] is True


def test_callback_rejects_mismatched_oauth_state(app, monkeypatch):
    monkeypatch.setattr(smartwatch_controller, 'current_user', SimpleNamespace(user_id=22))

    with app.test_request_context('/smartwatch/callback?code=abc&state=bad-state', method='GET'):
        from flask import session

        session['smartwatch_oauth_state'] = 'good-state'
        session['smartwatch_oauth_provider'] = 'google_fit'

        response = smartwatch_controller.callback.__wrapped__()

    assert response.status_code == 302
    assert '/smartwatch/integration?' in response.location
    assert 'status=error' in response.location


def test_callback_accepts_matching_oauth_state_and_calls_service(app, monkeypatch):
    monkeypatch.setattr(smartwatch_controller, 'current_user', SimpleNamespace(user_id=77))
    captured = {}

    def fake_handle_oauth_callback(user_id, provider, code):
        captured['user_id'] = user_id
        captured['provider'] = provider
        captured['code'] = code
        return {
            'success': True,
            'message': 'ok',
            'status_code': 200,
        }

    monkeypatch.setattr(
        smartwatch_controller.smartwatch_service,
        'handle_oauth_callback',
        fake_handle_oauth_callback,
    )

    with app.test_request_context('/smartwatch/callback?code=abc123&state=phms-smartwatch-google_fit-77:77', method='GET'):
        from flask import session

        session['smartwatch_oauth_state'] = 'phms-smartwatch-google_fit-77:77'
        session['smartwatch_oauth_provider'] = 'google_fit'

        response = smartwatch_controller.callback.__wrapped__()

    assert response.status_code == 302
    assert 'status=success' in response.location
    assert captured == {
        'user_id': 77,
        'provider': 'google_fit',
        'code': 'abc123',
    }


def test_callback_rejects_when_provider_cannot_be_resolved(app, monkeypatch):
    monkeypatch.setattr(smartwatch_controller, 'current_user', SimpleNamespace(user_id=88))
    called = {'service_called': False}

    def fake_handle_oauth_callback(user_id, provider, code):
        called['service_called'] = True
        return {'success': True, 'status_code': 200}

    monkeypatch.setattr(
        smartwatch_controller.smartwatch_service,
        'handle_oauth_callback',
        fake_handle_oauth_callback,
    )

    with app.test_request_context('/smartwatch/callback?code=abc123&state=opaque-state', method='GET'):
        from flask import session

        session['smartwatch_oauth_state'] = 'opaque-state'
        # Intentionally omit smartwatch_oauth_provider to simulate missing provider context.

        response = smartwatch_controller.callback.__wrapped__()

    assert response.status_code == 302
    assert '/smartwatch/integration?' in response.location
    assert 'status=error' in response.location
    assert called['service_called'] is False


def test_pre_sync_diagnostics_transports_query_params_to_service(app, monkeypatch):
    captured = {}

    def fake_pre_sync(user_id, provider, cursor=None, since=None):
        captured['user_id'] = user_id
        captured['provider'] = provider
        captured['cursor'] = cursor
        captured['since'] = since
        return {
            'success': True,
            'message': 'ok',
            'status_code': 200,
            'diagnostics': {
                'non_zero_metric_families': ['steps'],
                'metric_point_totals': {
                    'steps': 1,
                    'heart_rate': 0,
                    'temperature': 0,
                    'sleep_hours': 0,
                    'blood_pressure': 0,
                    'sugar': 0,
                },
            },
        }

    monkeypatch.setattr(smartwatch_controller.smartwatch_service, 'get_pre_sync_diagnostics', fake_pre_sync)
    monkeypatch.setattr(smartwatch_controller, 'current_user', SimpleNamespace(user_id=123))

    with app.test_request_context(
        '/smartwatch/pre-sync-diagnostics/google_fit?cursor=cursor-1&since=2026-03-20T00:00:00Z',
        method='GET',
    ):
        response, status_code = smartwatch_controller.pre_sync_diagnostics.__wrapped__('google_fit')

    assert status_code == 200
    assert response.get_json()['success'] is True
    assert captured == {
        'user_id': 123,
        'provider': 'google_fit',
        'cursor': 'cursor-1',
        'since': '2026-03-20T00:00:00Z',
    }
