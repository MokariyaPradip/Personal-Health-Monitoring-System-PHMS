from flask import render_template, redirect
from flask_login import login_required


@login_required
def reports():
    """Display reports page"""
    return render_template('reports.html')
