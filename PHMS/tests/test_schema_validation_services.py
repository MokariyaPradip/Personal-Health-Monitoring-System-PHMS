def test_health_service_rejects_non_numeric_heart_rate(app):
    from services import health_service

    with app.app_context():
        result = health_service.add_health(1, {'heart_rate': 'abc'})

    assert result['status_code'] == 400
    assert result['message'] == 'Heart rate must be a valid number'


def test_medication_service_rejects_invalid_date_format():
    from services import medication_service

    result = medication_service.add_medication(
        1,
        {
            'medicine_name': 'Aspirin',
            'dosage': '10mg',
            'frequency': 1,
            'start_date': '01-01-2030',
            'end_date': '2030-01-02',
        },
    )

    assert result['status_code'] == 400
    assert result['message'] == 'Invalid date format. Use YYYY-MM-DD.'


def test_auth_service_register_validates_email_format():
    from services import auth_service

    result = auth_service.register(
        {
            'username': 'validuser',
            'email': 'invalid-email',
            'password': 'Password123',
        }
    )

    assert result['status_code'] == 400
    assert result['message'] == 'Invalid email format'


def test_auth_service_reset_password_requires_email():
    from services import auth_service

    result = auth_service.reset_password({})

    assert result['status_code'] == 400
    assert result['message'] == 'Email is required'
