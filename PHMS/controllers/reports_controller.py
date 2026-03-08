from flask import render_template, redirect
from flask_login import login_required


@login_required
def reports():
    """Display health and medication reports page.
    
    Renders the reports page which provides analytical views and visualizations
    of user's health data and medication adherence. The actual report generation
    and data visualization logic is handled via JavaScript on the frontend and
    separate API endpoints in the reports module.
    
    Endpoints:
        GET /reports: Display reports page
    
    Features (Frontend-driven):
        - Health data trends and visualizations
        - Medication adherence statistics
        - Exportable reports (PDF generation)
        - Date range filtering
        - Comparative health metrics
    
    Returns:
        Rendered reports.html template
    
    Security:
        - Requires @login_required (authenticated session)
        - Report data scoped to current_user via API endpoints
    
    Note:
        This is a view-only endpoint. Actual report data is fetched via
        AJAX calls to /reports/api/* endpoints defined in reports/routes/
    """
    return render_template('reports.html')
