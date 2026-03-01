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
