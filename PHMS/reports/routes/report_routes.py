from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO, StringIO
import csv

from flask import Blueprint, jsonify, render_template, request, send_file, Response
from flask_login import current_user, login_required

from reports.pdf.pdf_generator import generate_report_pdf
from reports.services.report_service import ReportDateRange, build_report_for_range


reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


def _parse_date(value: str | None) -> date | None:
    """Parse ISO date string (YYYY-MM-DD) to date object.
    
    Args:
        value (str | None): Date string in ISO format or None
    
    Returns:
        date | None: Parsed date object, or None if value is None or invalid format
    
    Example:
        >>> _parse_date('2026-03-08')
        date(2026, 3, 8)
        >>> _parse_date('invalid')
        None
        >>> _parse_date(None)
        None
    """
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _resolve_period(report_type: str) -> ReportDateRange:
    """Resolve predefined report type to date range.
    
    Converts report type string to ReportDateRange with appropriate start and end dates
    relative to today.
    
    Args:
        report_type (str): Report period identifier
            - 'weekly': Last 7 days (today - 6 days to today)
            - 'monthly': Last 30 days (today - 29 days to today)
            - 'yearly': Last 365 days (today - 364 days to today)
    
    Returns:
        ReportDateRange: Date range object with start_date and end_date
    
    Raises:
        ValueError: If report_type is not supported
    
    Example:
        >>> # On 2026-03-08
        >>> dr = _resolve_period('weekly')
        >>> dr.start_date
        date(2026, 3, 2)  # 7 days ago
        >>> dr.end_date
        date(2026, 3, 8)  # today
    """
    today = date.today()
    if report_type == "weekly":
        return ReportDateRange(start_date=today - timedelta(days=6), end_date=today)
    if report_type == "monthly":
        return ReportDateRange(start_date=today - timedelta(days=29), end_date=today)
    if report_type == "yearly":
        return ReportDateRange(start_date=today - timedelta(days=364), end_date=today)
    raise ValueError("Unsupported report type")


def _wants_json() -> bool:
    """Determine if client wants JSON response based on request parameters.
    
    Checks multiple indicators to determine JSON preference:
    1. Query parameter format=json
    2. URL path ending with /json
    3. Accept header preferring application/json over text/html
    
    Returns:
        bool: True if JSON response preferred, False otherwise
    
    Example:
        >>> # Request: /reports/weekly?format=json
        >>> _wants_json()
        True
        >>> # Request: /reports/weekly with Accept: application/json
        >>> _wants_json()
        True
    """
    requested = (request.args.get("format") or "").lower()
    if requested == "json":
        return True
    if request.path.endswith("/json"):
        return True
    best = request.accept_mimetypes.best
    return best == "application/json" and request.accept_mimetypes[best] > request.accept_mimetypes["text/html"]


def _wants_csv() -> bool:
    """Check if client requested CSV export format.
    
    Returns:
        bool: True if format=csv query parameter present, False otherwise
    
    Example:
        >>> # Request: /reports/monthly?format=csv
        >>> _wants_csv()
        True
    """
    requested = (request.args.get("format") or "").lower()
    return requested == "csv"


def _generate_csv(report_data: dict) -> str:
    """Generate CSV export from report data dictionary.
    
    Converts comprehensive report data into CSV format with sections for metadata,
    summary statistics, trends, risk indicators, medication adherence, alerts,
    and ML predictions.
    
    Args:
        report_data (dict): Complete report data from build_report_for_range()
    
    Returns:
        str: CSV formatted string with all report sections
    
    CSV Structure:
        - Header section (user, report type, date range, generation time)
        - Summary Statistics (metric, avg, min, max)
        - Trend Comparison (metric, current avg, previous avg, % change)
        - Risk Indicators (metric, avg, risk level)
        - Medication Adherence (scheduled, taken, percentage)
        - Alert Summary (total, critical)
        - ML Classifier Distribution (Low/Medium/High risk counts)
    
    Example:
        >>> csv_data = _generate_csv(report_data)
        >>> print(csv_data[:50])
        'PHMS Health Report\nUser,john_doe\nReport Type,Weekly'
    """
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    meta = report_data.get("meta", {})
    user = report_data.get("user", {})
    writer.writerow(["PHMS Health Report"])
    writer.writerow(["User", user.get("username", "N/A")])
    writer.writerow(["Report Type", meta.get("report_type", "custom").title()])
    writer.writerow(["Date Range", f"{meta.get('start_date')} to {meta.get('end_date')}"])
    writer.writerow(["Records", meta.get("record_count", 0)])
    writer.writerow(["Generated At", meta.get("generated_at", "")])
    writer.writerow([])
    
    # Summary Statistics
    writer.writerow(["Summary Statistics"])
    writer.writerow(["Metric", "Average", "Minimum", "Maximum"])
    for metric, stats in report_data.get("summary_statistics", {}).items():
        writer.writerow([
            metric,
            stats.get("avg", ""),
            stats.get("min", ""),
            stats.get("max", "")
        ])
    writer.writerow([])
    
    # Trend Analysis
    writer.writerow(["Trend Comparison"])
    writer.writerow(["Metric", "Current Avg", "Previous Avg", "% Change"])
    for metric, stats in report_data.get("trend_analysis", {}).items():
        writer.writerow([
            metric,
            stats.get("current_avg", ""),
            stats.get("previous_avg", ""),
            stats.get("pct_change", "")
        ])
    writer.writerow([])
    
    # Risk Indicators
    writer.writerow(["Risk Indicators"])
    writer.writerow(["Metric", "Average", "Risk Level"])
    for metric, stats in report_data.get("risk_indicators", {}).items():
        writer.writerow([
            metric,
            stats.get("avg", ""),
            stats.get("status", "")
        ])
    writer.writerow([])
    
    # Medication Adherence
    writer.writerow(["Medication Adherence"])
    med = report_data.get("medication_adherence", {})
    writer.writerow(["Total Scheduled Doses", med.get("total_scheduled_doses", 0)])
    writer.writerow(["Total Taken Doses", med.get("total_taken_doses", 0)])
    writer.writerow(["Adherence Percentage", f"{med.get('adherence_percentage', 0)}%"])
    writer.writerow([])
    
    # Alert Summary
    writer.writerow(["Alerts Summary"])
    alerts = report_data.get("alert_summary", {})
    writer.writerow(["Total Alerts", alerts.get("total_alerts", 0)])
    writer.writerow(["Critical Alerts", alerts.get("critical_alerts", 0)])
    writer.writerow([])
    
    # ML Classifier Distribution
    writer.writerow(["ML Classifier Risk Distribution"])
    ml_dist = report_data.get("ml_classifier_distribution", {})
    writer.writerow(["Low Risk Predictions", ml_dist.get("Low Risk", 0)])
    writer.writerow(["Medium Risk Predictions", ml_dist.get("Medium Risk", 0)])
    writer.writerow(["High Risk Predictions", ml_dist.get("High Risk", 0)])
    writer.writerow(["Total Predictions", ml_dist.get("total_predictions", 0)])
    
    return output.getvalue()


def _build_response(report_data: dict):
    """Build appropriate HTTP response based on client's requested format.
    
    Routes to CSV, JSON, or HTML response based on request headers and query params.
    
    Args:
        report_data (dict): Complete report data dictionary
    
    Returns:
        Response: Flask response object
            - CSV download (text/csv) if format=csv
            - JSON (application/json) if format=json or Accept header
            - HTML page (text/html) otherwise (default)
    
    Example:
        >>> # CSV request
        >>> response = _build_response(report_data)
        >>> response.mimetype
        'text/csv'
        
        >>> # JSON request
        >>> response = _build_response(report_data)
        >>> response.mimetype
        'application/json'
    """
    if _wants_csv():
        csv_data = _generate_csv(report_data)
        meta = report_data.get("meta", {})
        filename = f"phms_report_{meta.get('report_type', 'custom')}_{meta.get('start_date')}_{meta.get('end_date')}.csv"
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    if _wants_json():
        return jsonify(report_data)
    return render_template("reports.html", report_data=report_data)


@reports_bp.route("", methods=["GET"])
@login_required
def reports_home():
    """Display default monthly health report.
    
    Landing page for reports section, shows last 30 days of health data by default.
    Supports feature filtering via query parameter.
    
    Endpoints:
        GET /reports: Display monthly report (default)
    
    Query Parameters:
        feature (str, optional): Filter metrics by category (default: 'all')
            - 'all': All metrics
            - 'vital': Heart rate, BP, sugar, temperature, health scores
            - 'activity': Steps, sleep, heart rate, health scores
            - 'medication': Sugar, BP, health scores
            - 'chronic': Sugar, BP, heart rate, health scores
        format (str, optional): Response format ('json', 'csv', or omit for HTML)
    
    Returns:
        Response: HTML page, JSON, or CSV based on format parameter
    
    Security:
        - Requires @login_required
        - Data scoped to current_user.user_id
    """
    feature_filter = request.args.get("feature", "all").lower()
    report_data = build_report_for_range(
        user_id=current_user.user_id,
        report_type="monthly",
        dr=_resolve_period("monthly"),
        feature_filter=feature_filter,
    )
    return _build_response(report_data)


@reports_bp.route("/weekly", methods=["GET"])
@login_required
def weekly_report():
    """Generate health report for the last 7 days.
    
    Endpoints:
        GET /reports/weekly: Weekly health summary
    
    Query Parameters:
        feature (str, optional): Metric filter category (default: 'all')
        format (str, optional): Response format ('json', 'csv', or HTML)
    
    Returns:
        Response: Weekly report in requested format (HTML/JSON/CSV)
    
    Security:
        - Requires @login_required
        - Data filtered by current_user.user_id
    """
    feature_filter = request.args.get("feature", "all").lower()
    report_data = build_report_for_range(
        user_id=current_user.user_id,
        report_type="weekly",
        dr=_resolve_period("weekly"),
        feature_filter=feature_filter,
    )
    return _build_response(report_data)


@reports_bp.route("/monthly", methods=["GET"])
@login_required
def monthly_report():
    """Generate health report for the last 30 days.
    
    Endpoints:
        GET /reports/monthly: Monthly health summary
    
    Query Parameters:
        feature (str, optional): Metric filter category (default: 'all')
        format (str, optional): Response format ('json', 'csv', or HTML)
    
    Returns:
        Response: Monthly report in requested format (HTML/JSON/CSV)
    
    Security:
        - Requires @login_required
        - Data filtered by current_user.user_id
    """
    feature_filter = request.args.get("feature", "all").lower()
    report_data = build_report_for_range(
        user_id=current_user.user_id,
        report_type="monthly",
        dr=_resolve_period("monthly"),
        feature_filter=feature_filter,
    )
    return _build_response(report_data)


@reports_bp.route("/yearly", methods=["GET"])
@login_required
def yearly_report():
    """Generate health report for the last 365 days.
    
    Endpoints:
        GET /reports/yearly: Yearly health summary
    
    Query Parameters:
        feature (str, optional): Metric filter category (default: 'all')
        format (str, optional): Response format ('json', 'csv', or HTML)
    
    Returns:
        Response: Yearly report in requested format (HTML/JSON/CSV)
    
    Security:
        - Requires @login_required
        - Data filtered by current_user.user_id
    """
    feature_filter = request.args.get("feature", "all").lower()
    report_data = build_report_for_range(
        user_id=current_user.user_id,
        report_type="yearly",
        dr=_resolve_period("yearly"),
        feature_filter=feature_filter,
    )
    return _build_response(report_data)


@reports_bp.route("/custom", methods=["GET"])
@login_required
def custom_report():
    """Generate health report for custom date range.
    
    Allows users to specify arbitrary start and end dates for flexible reporting.
    
    Endpoints:
        GET /reports/custom: Custom date range report
    
    Query Parameters:
        start_date (str, required): Start date in YYYY-MM-DD format
        end_date (str, required): End date in YYYY-MM-DD format
        feature (str, optional): Metric filter category (default: 'all')
        format (str, optional): Response format ('json', 'csv', or HTML)
    
    Returns:
        Response: Custom report in requested format (HTML/JSON/CSV)
        400: If start_date or end_date missing or invalid
        400: If start_date > end_date
    
    Example:
        GET /reports/custom?start_date=2026-01-01&end_date=2026-01-31&feature=vital&format=json
    
    Security:
        - Requires @login_required
        - Data filtered by current_user.user_id
    """
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))
    feature_filter = request.args.get("feature", "all").lower()

    if not start_date or not end_date:
        return jsonify({"error": "start_date and end_date are required (YYYY-MM-DD)"}), 400
    if start_date > end_date:
        return jsonify({"error": "start_date cannot be greater than end_date"}), 400

    report_data = build_report_for_range(
        user_id=current_user.user_id,
        report_type="custom",
        dr=ReportDateRange(start_date=start_date, end_date=end_date),
        feature_filter=feature_filter,
    )
    return _build_response(report_data)


@reports_bp.route("/<string:report_type>/pdf", methods=["GET"])
@login_required
def report_pdf(report_type: str):
    """Generate downloadable PDF version of health report.
    
    Creates professionally formatted PDF report using ReportLab library with
    visual design, tables, and color-coded risk indicators.
    
    Endpoints:
        GET /reports/<report_type>/pdf: Download PDF report
    
    Path Parameters:
        report_type (str): Report period type
            - 'weekly', 'monthly', 'yearly': Predefined periods
            - 'custom': Requires start_date and end_date query params
    
    Query Parameters:
        feature (str, optional): Metric filter category (default: 'all')
        start_date (str, required for custom): Start date YYYY-MM-DD
        end_date (str, required for custom): End date YYYY-MM-DD
    
    Returns:
        Response: PDF file download (application/pdf)
        400: If report_type is invalid or custom dates missing/invalid
        500: If PDF generation fails (e.g., ReportLab not installed)
    
    PDF Contents:
        - Patient profile with BMI and demographics
        - KPI snapshot cards (adherence, alerts, health score)
        - Risk mix summary
        - Detailed statistics tables
        - Trend analysis
        - Medication adherence
        - ML predictions distribution
    
    Example:
        GET /reports/monthly/pdf
        GET /reports/custom/pdf?start_date=2026-01-01&end_date=2026-01-31
    
    Security:
        - Requires @login_required
        - Data filtered by current_user.user_id
    
    Note:
        - Requires reportlab library (raises 500 error with instructions if missing)
        - PDF filename includes report type and date range
    """
    feature_filter = request.args.get("feature", "all").lower()

    if report_type in {"weekly", "monthly", "yearly"}:
        dr = _resolve_period(report_type)
    elif report_type == "custom":
        start_date = _parse_date(request.args.get("start_date"))
        end_date = _parse_date(request.args.get("end_date"))
        if not start_date or not end_date:
            return jsonify({"error": "start_date and end_date are required for custom PDF"}), 400
        if start_date > end_date:
            return jsonify({"error": "start_date cannot be greater than end_date"}), 400
        dr = ReportDateRange(start_date=start_date, end_date=end_date)
    else:
        return jsonify({"error": "Invalid report type"}), 400

    report_data = build_report_for_range(
        user_id=current_user.user_id,
        report_type=report_type,
        dr=dr,
        feature_filter=feature_filter,
    )

    try:
        pdf_bytes = generate_report_pdf(report_data)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500

    file_name = f"phms_{report_type}_report_{dr.start_date.isoformat()}_{dr.end_date.isoformat()}.pdf"
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=file_name,
    )
