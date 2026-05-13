from types import SimpleNamespace


def test_profile_schema_rejects_out_of_range_age():
    from schemas.profile_schema import validate_profile_payload

    model, errors = validate_profile_payload({
        'username': 'alice',
        'gender': 'Female',
        'age': 0,
        'height': 165,
        'weight': 55,
    })

    assert model is None
    assert isinstance(errors, dict)
    assert 'age' in errors


def test_profile_service_update_returns_structured_validation_errors(monkeypatch):
    from services import profile_service

    user = SimpleNamespace(
        user_id=101,
        username='alice',
        gender='Female',
        age=25,
        height=165.0,
        weight=55.0,
        bmi=20.2,
    )

    committed = {'value': False}

    monkeypatch.setattr(profile_service.db.session, 'get', lambda *_args, **_kwargs: user)

    def fake_commit():
        committed['value'] = True

    monkeypatch.setattr(profile_service.db.session, 'commit', fake_commit)

    result = profile_service.update_profile(
        101,
        {
            'username': 'alice',
            'gender': 'Female',
            'age': 999,
            'height': 165,
            'weight': 55,
        },
    )

    assert result['success'] is False
    assert result['status_code'] == 400
    assert 'errors' in result
    assert 'age' in result['errors']
    assert committed['value'] is False


def test_profile_service_update_success_returns_updated_payload(monkeypatch):
    from services import profile_service

    user = SimpleNamespace(
        user_id=202,
        username='old-name',
        gender='Male',
        age=30,
        height=170.0,
        weight=70.0,
        bmi=24.2,
    )

    monkeypatch.setattr(profile_service.db.session, 'get', lambda *_args, **_kwargs: user)
    monkeypatch.setattr(profile_service.db.session, 'commit', lambda: None)

    result = profile_service.update_profile(
        202,
        {
            'username': 'new-name',
            'gender': 'Other',
            'age': 31,
            'height': 171.5,
            'weight': 71.2,
        },
    )

    assert result['success'] is True
    assert result['message'] == 'Profile updated successfully'
    assert result['updated']['username'] == 'new-name'
    assert result['updated']['gender'] == 'Other'
    assert result['updated']['age'] == 31
    assert result['updated']['height'] == 171.5
    assert result['updated']['weight'] == 71.2
