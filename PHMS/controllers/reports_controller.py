from flask import render_template, session, redirect


def reports():
    """Display reports page"""
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('reports.html')
