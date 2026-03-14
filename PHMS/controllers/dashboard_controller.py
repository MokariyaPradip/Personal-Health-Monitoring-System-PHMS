from flask import render_template
from flask_login import current_user, login_required

from services import dashboard_service


@login_required
def dashboard():
    context = dashboard_service.dashboard(current_user.user_id)
    return render_template('dashboard.html', **context)


__all__ = ['dashboard']
