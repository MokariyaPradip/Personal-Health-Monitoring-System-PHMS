import inspect
from types import SimpleNamespace


def test_profile_update_rejects_missing_csrf(app):
    from controllers import profile_controller

    update_fn = inspect.unwrap(profile_controller.update_profile)

    with app.test_request_context('/update-profile', method='PUT', json={'username': 'alice'}):
        response, status_code = update_fn()

    assert status_code == 400
    payload = response.get_json()
    assert payload['success'] is False
    assert payload['message'] == 'Invalid CSRF token'


def test_profile_update_surfaces_structured_validation_errors(app, monkeypatch):
    from controllers import profile_controller

    update_fn = inspect.unwrap(profile_controller.update_profile)

    monkeypatch.setattr(profile_controller, 'current_user', SimpleNamespace(user_id=777))
    monkeypatch.setattr(profile_controller, 'validate_csrf', lambda _token: None)
    monkeypatch.setattr(
        profile_controller.profile_service,
        'update_profile',
        lambda _user_id, _payload: {
            'success': False,
            'message': 'Validation failed',
            'errors': {'age': 'Age must be between 1 and 150'},
            'status_code': 400,
        },
    )

    with app.test_request_context(
        '/update-profile',
        method='PUT',
        json={'username': 'alice', 'age': 999},
        headers={'X-CSRFToken': 'test-token'},
    ):
        response, status_code = update_fn()

    assert status_code == 400
    payload = response.get_json()
    assert payload['success'] is False
    assert payload['errors']['age'] == 'Age must be between 1 and 150'


def test_change_password_surfaces_service_validation_message(app, monkeypatch):
    from controllers import auth_controller

    change_fn = inspect.unwrap(auth_controller.change_password)

    monkeypatch.setattr(auth_controller, 'current_user', SimpleNamespace(user_id=55, password='hashed'))
    monkeypatch.setattr(auth_controller, 'validate_csrf', lambda _token: None)
    monkeypatch.setattr(
        auth_controller.auth_service,
        'change_password',
        lambda _user, _payload: {
            'success': False,
            'message': 'Current password is incorrect',
            'status_code': 400,
        },
    )

    with app.test_request_context(
        '/change-password',
        method='PUT',
        json={
            'current_password': 'wrong',
            'new_password': 'Password123',
            'confirm_password': 'Password123',
        },
        headers={'X-CSRFToken': 'test-token'},
    ):
        response, status_code = change_fn()

    assert status_code == 400
    payload = response.get_json()
    assert payload['success'] is False
    assert payload['message'] == 'Current password is incorrect'
