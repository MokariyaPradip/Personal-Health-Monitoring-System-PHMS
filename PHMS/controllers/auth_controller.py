from flask import jsonify, redirect, render_template, request
from flask_login import current_user, login_required, login_user, logout_user

from services import auth_service


def register():
    if request.method == 'GET':
        return render_template('register.html')

    payload = request.get_json(silent=True) or {}
    result = auth_service.register(payload)
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code


def login():
    if request.method == 'GET':
        return render_template('login.html')

    payload = request.get_json(silent=True) or {}
    result = auth_service.login(payload)
    status_code = result.pop('status_code', 200)

    user = result.pop('user', None)
    if result.get('success') and user is not None:
        login_user(user)

    return jsonify(result), status_code


@login_required
def logout():
    logout_user()
    return redirect('/login')


def forgot_password():
    if request.method == 'GET':
        return render_template('forgot_password.html')

    payload = request.get_json(silent=True) or {} if request.is_json else request.form.to_dict()
    result = auth_service.forgot_password(payload)
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code


def reset_password():
    if request.method == 'GET':
        return render_template('reset_password.html')

    payload = request.get_json(silent=True) or {} if request.is_json else request.form.to_dict()
    result = auth_service.reset_password(payload)
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code


@login_required
def change_password():
    payload = request.get_json(silent=True) or {}
    result = auth_service.change_password(current_user, payload)
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code


__all__ = [
    'register',
    'login',
    'logout',
    'forgot_password',
    'reset_password',
    'change_password',
]
