from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from io import BytesIO, StringIO

from flask import Response, jsonify, render_template, request, send_file
from flask_login import current_user, login_required

from services.report_pdf_service import generate_report_pdf
from services.report_service import ReportDateRange, build_report_for_range


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


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _resolve_period(report_type: str) -> ReportDateRange:
    today = date.today()
    if report_type == "weekly":
        return ReportDateRange(start_date=today - timedelta(days=6), end_date=today)
    if report_type == "monthly":
        return ReportDateRange(start_date=today - timedelta(days=29), end_date=today)
    if report_type == "yearly":
        return ReportDateRange(start_date=today - timedelta(days=364), end_date=today)
    raise ValueError("Unsupported report type")


def _wants_json() -> bool:
    requested = (request.args.get("format") or "").lower()
    if requested == "json":
        return True
    if request.path.endswith("/json"):
        return True
    best = request.accept_mimetypes.best
    return best == "application/json" and request.accept_mimetypes[best] > request.accept_mimetypes["text/html"]


def _wants_csv() -> bool:
    requested = (request.args.get("format") or "").lower()
    return requested == "csv"


def _generate_csv(report_data: dict) -> str:
    output = StringIO()
    writer = csv.writer(output)

    meta = report_data.get("meta", {})
    user = report_data.get("user", {})
    writer.writerow(["PHMS Health Report"])
    writer.writerow(["User", user.get("username", "N/A")])
    writer.writerow(["Report Type", meta.get("report_type", "custom").title()])
    writer.writerow(["Date Range", f"{meta.get('start_date')} to {meta.get('end_date')}"])
    writer.writerow(["Records", meta.get("record_count", 0)])
    writer.writerow(["Generated At", meta.get("generated_at", "")])
    writer.writerow([])

    writer.writerow(["Summary Statistics"])
    writer.writerow(["Metric", "Average", "Minimum", "Maximum"])
    for metric, stats in report_data.get("summary_statistics", {}).items():
        writer.writerow([
            metric,
            stats.get("avg", ""),
            stats.get("min", ""),
            stats.get("max", ""),
        ])
    writer.writerow([])

    writer.writerow(["Trend Comparison"])
    writer.writerow(["Metric", "Current Avg", "Previous Avg", "% Change"])
    for metric, stats in report_data.get("trend_analysis", {}).items():
        writer.writerow([
            metric,
            stats.get("current_avg", ""),
            stats.get("previous_avg", ""),
            stats.get("pct_change", ""),
        ])
    writer.writerow([])

    writer.writerow(["Risk Indicators"])
    writer.writerow(["Metric", "Average", "Risk Level"])
    for metric, stats in report_data.get("risk_indicators", {}).items():
        writer.writerow([
            metric,
            stats.get("avg", ""),
            stats.get("status", ""),
        ])
    writer.writerow([])

    writer.writerow(["Medication Adherence"])
    med = report_data.get("medication_adherence", {})
    writer.writerow(["Total Scheduled Doses", med.get("total_scheduled_doses", 0)])
    writer.writerow(["Total Taken Doses", med.get("total_taken_doses", 0)])
    writer.writerow(["Adherence Percentage", f"{med.get('adherence_percentage', 0)}%"])
    writer.writerow([])

    writer.writerow(["Alerts Summary"])
    alerts = report_data.get("alert_summary", {})
    writer.writerow(["Total Alerts", alerts.get("total_alerts", 0)])
    writer.writerow(["Critical Alerts", alerts.get("critical_alerts", 0)])
    writer.writerow([])

    writer.writerow(["ML Classifier Risk Distribution"])
    ml_dist = report_data.get("ml_classifier_distribution", {})
    writer.writerow(["Low Risk Predictions", ml_dist.get("Low Risk", 0)])
    writer.writerow(["Medium Risk Predictions", ml_dist.get("Medium Risk", 0)])
    writer.writerow(["High Risk Predictions", ml_dist.get("High Risk", 0)])
    writer.writerow(["Total Predictions", ml_dist.get("total_predictions", 0)])

    return output.getvalue()


def _build_response(report_data: dict):
    if _wants_csv():
        csv_data = _generate_csv(report_data)
        meta = report_data.get("meta", {})
        filename = f"phms_report_{meta.get('report_type', 'custom')}_{meta.get('start_date')}_{meta.get('end_date')}.csv"
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    if _wants_json():
        return jsonify(report_data)
    return render_template("reports.html", report_data=report_data)


def _feature_filter() -> str:
    return request.args.get("feature", "all").lower()


@login_required
def reports_home():
    report_data = build_report_for_range(
        user_id=current_user.user_id,
        report_type="monthly",
        dr=_resolve_period("monthly"),
        feature_filter=_feature_filter(),
    )
    return _build_response(report_data)


@login_required
def weekly_report():
    report_data = build_report_for_range(
        user_id=current_user.user_id,
        report_type="weekly",
        dr=_resolve_period("weekly"),
        feature_filter=_feature_filter(),
    )
    return _build_response(report_data)


@login_required
def monthly_report():
    report_data = build_report_for_range(
        user_id=current_user.user_id,
        report_type="monthly",
        dr=_resolve_period("monthly"),
        feature_filter=_feature_filter(),
    )
    return _build_response(report_data)


@login_required
def yearly_report():
    report_data = build_report_for_range(
        user_id=current_user.user_id,
        report_type="yearly",
        dr=_resolve_period("yearly"),
        feature_filter=_feature_filter(),
    )
    return _build_response(report_data)


@login_required
def custom_report():
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))
    if not start_date or not end_date:
        return jsonify({"error": "start_date and end_date are required (YYYY-MM-DD)"}), 400
    if start_date > end_date:
        return jsonify({"error": "start_date cannot be greater than end_date"}), 400

    report_data = build_report_for_range(
        user_id=current_user.user_id,
        report_type="custom",
        dr=ReportDateRange(start_date=start_date, end_date=end_date),
        feature_filter=_feature_filter(),
    )
    return _build_response(report_data)


@login_required
def report_pdf(report_type: str):
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
        feature_filter=_feature_filter(),
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
