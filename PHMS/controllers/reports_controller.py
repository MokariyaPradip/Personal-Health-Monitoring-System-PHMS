from __future__ import annotations

import csv
import hashlib
import json
import threading
import time
from datetime import date, datetime, timedelta
from io import BytesIO, StringIO

from flask import Response, jsonify, render_template, request, send_file, stream_with_context
from flask_login import current_user, login_required

from services.report_pdf_service import generate_report_pdf
from services.report_service import ReportDateRange, build_report_for_range
from repositories.report_repository import ReportRepository


# In-process TTL caches for report payload and generated PDF bytes.
_REPORT_CACHE: dict[str, tuple[float, dict]] = {}
_PDF_CACHE: dict[str, tuple[float, bytes]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SECONDS = 300
_CACHE_MAX_ITEMS = 128


def _cache_get(cache: dict, key: str):
    now = time.time()
    with _CACHE_LOCK:
        payload = cache.get(key)
        if not payload:
            return None
        expires_at, value = payload
        if expires_at <= now:
            cache.pop(key, None)
            return None
        return value


def _cache_set(cache: dict, key: str, value):
    expires_at = time.time() + _CACHE_TTL_SECONDS
    with _CACHE_LOCK:
        cache[key] = (expires_at, value)
        if len(cache) > _CACHE_MAX_ITEMS:
            # Remove expired first; if still too large remove oldest inserted item.
            now = time.time()
            expired_keys = [k for k, (exp, _) in cache.items() if exp <= now]
            for old_key in expired_keys:
                cache.pop(old_key, None)
            while len(cache) > _CACHE_MAX_ITEMS:
                cache.pop(next(iter(cache)), None)


def _report_cache_key(user_id: int, report_type: str, dr: ReportDateRange, feature_filter: str) -> str:
    raw = f"{user_id}|{report_type}|{dr.start_date.isoformat()}|{dr.end_date.isoformat()}|{feature_filter}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _get_report_data_cached(user_id: int, report_type: str, dr: ReportDateRange, feature_filter: str) -> dict:
    key = _report_cache_key(user_id=user_id, report_type=report_type, dr=dr, feature_filter=feature_filter)
    cached = _cache_get(_REPORT_CACHE, key)
    if cached is not None:
        return cached

    report_data = build_report_for_range(
        user_id=user_id,
        report_type=report_type,
        dr=dr,
        feature_filter=feature_filter,
    )
    _cache_set(_REPORT_CACHE, key, report_data)
    return report_data


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
    writer.writerow([])

    writer.writerow(["Data Source Summary"])
    source = report_data.get("source_summary", {})
    writer.writerow(["Manual Records", source.get("manual_count", 0)])
    writer.writerow(["Google Fit Records", source.get("google_fit_count", 0)])
    writer.writerow(["Smartwatch Records (Total)", source.get("smartwatch_total", 0)])
    writer.writerow(["Other Source Records", source.get("other_count", 0)])
    writer.writerow(["Manual %", f"{source.get('manual_pct', 0)}%"])
    writer.writerow(["Smartwatch %", f"{source.get('smartwatch_pct', 0)}%"])
    writer.writerow(["Dominant Source", source.get("dominant_source", "none")])

    return output.getvalue()


def _iter_csv_chunks(report_data: dict):
    """Yield CSV in chunks to avoid building a single large in-memory string."""
    def write_row(row):
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(row)
        return buffer.getvalue()

    meta = report_data.get("meta", {})
    user = report_data.get("user", {})

    rows = [
        ["PHMS Health Report"],
        ["User", user.get("username", "N/A")],
        ["Report Type", meta.get("report_type", "custom").title()],
        ["Date Range", f"{meta.get('start_date')} to {meta.get('end_date')}"] ,
        ["Records", meta.get("record_count", 0)],
        ["Generated At", meta.get("generated_at", "")],
        [],
        ["Summary Statistics"],
        ["Metric", "Average", "Minimum", "Maximum"],
    ]
    for row in rows:
        yield write_row(row)

    for metric, stats in report_data.get("summary_statistics", {}).items():
        yield write_row([metric, stats.get("avg", ""), stats.get("min", ""), stats.get("max", "")])

    yield write_row([])
    yield write_row(["Trend Comparison"])
    yield write_row(["Metric", "Current Avg", "Previous Avg", "% Change"])
    for metric, stats in report_data.get("trend_analysis", {}).items():
        yield write_row([metric, stats.get("current_avg", ""), stats.get("previous_avg", ""), stats.get("pct_change", "")])

    yield write_row([])
    yield write_row(["Risk Indicators"])
    yield write_row(["Metric", "Average", "Risk Level"])
    for metric, stats in report_data.get("risk_indicators", {}).items():
        yield write_row([metric, stats.get("avg", ""), stats.get("status", "")])

    yield write_row([])
    yield write_row(["Medication Adherence"])
    med = report_data.get("medication_adherence", {})
    yield write_row(["Total Scheduled Doses", med.get("total_scheduled_doses", 0)])
    yield write_row(["Total Taken Doses", med.get("total_taken_doses", 0)])
    yield write_row(["Adherence Percentage", f"{med.get('adherence_percentage', 0)}%"])

    yield write_row([])
    yield write_row(["Alerts Summary"])
    alerts = report_data.get("alert_summary", {})
    yield write_row(["Total Alerts", alerts.get("total_alerts", 0)])
    yield write_row(["Critical Alerts", alerts.get("critical_alerts", 0)])

    yield write_row([])
    yield write_row(["ML Classifier Risk Distribution"])
    ml_dist = report_data.get("ml_classifier_distribution", {})
    yield write_row(["Low Risk Predictions", ml_dist.get("Low Risk", 0)])
    yield write_row(["Medium Risk Predictions", ml_dist.get("Medium Risk", 0)])
    yield write_row(["High Risk Predictions", ml_dist.get("High Risk", 0)])
    yield write_row(["Total Predictions", ml_dist.get("total_predictions", 0)])

    yield write_row([])
    yield write_row(["Data Source Summary"])
    source = report_data.get("source_summary", {})
    yield write_row(["Manual Records", source.get("manual_count", 0)])
    yield write_row(["Google Fit Records", source.get("google_fit_count", 0)])
    yield write_row(["Smartwatch Records (Total)", source.get("smartwatch_total", 0)])
    yield write_row(["Other Source Records", source.get("other_count", 0)])
    yield write_row(["Manual %", f"{source.get('manual_pct', 0)}%"])
    yield write_row(["Smartwatch %", f"{source.get('smartwatch_pct', 0)}%"])
    yield write_row(["Dominant Source", source.get("dominant_source", "none")])


def _iter_json_chunks(payload: dict):
    """Yield encoded JSON chunks using iterencode for streaming."""
    encoder = json.JSONEncoder(separators=(",", ":"), ensure_ascii=False)
    for chunk in encoder.iterencode(payload):
        yield chunk


def _build_response(report_data: dict):
    meta = report_data.get("meta", {})
    record_count = int(meta.get("record_count", 0) or 0)

    if _wants_csv():
        filename = f"phms_report_{meta.get('report_type', 'custom')}_{meta.get('start_date')}_{meta.get('end_date')}.csv"
        # Stream large exports to reduce peak memory and response blocking.
        if record_count >= 1000:
            return Response(
                stream_with_context(_iter_csv_chunks(report_data)),
                mimetype="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )

        csv_data = _generate_csv(report_data)
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    if _wants_json():
        if record_count >= 1000:
            return Response(
                stream_with_context(_iter_json_chunks(report_data)),
                mimetype="application/json",
            )
        return jsonify(report_data)

    return render_template("reports.html", report_data=report_data)


def _feature_filter() -> str:
    return request.args.get("feature", "all").lower()


@login_required
def reports_home():
    dr = _resolve_period("monthly")
    feature = _feature_filter()
    report_data = _get_report_data_cached(
        user_id=current_user.user_id,
        report_type="monthly",
        dr=dr,
        feature_filter=feature,
    )
    return _build_response(report_data)


@login_required
def weekly_report():
    dr = _resolve_period("weekly")
    feature = _feature_filter()
    report_data = _get_report_data_cached(
        user_id=current_user.user_id,
        report_type="weekly",
        dr=dr,
        feature_filter=feature,
    )
    return _build_response(report_data)


@login_required
def monthly_report():
    dr = _resolve_period("monthly")
    feature = _feature_filter()
    report_data = _get_report_data_cached(
        user_id=current_user.user_id,
        report_type="monthly",
        dr=dr,
        feature_filter=feature,
    )
    return _build_response(report_data)


@login_required
def yearly_report():
    dr = _resolve_period("yearly")
    feature = _feature_filter()
    report_data = _get_report_data_cached(
        user_id=current_user.user_id,
        report_type="yearly",
        dr=dr,
        feature_filter=feature,
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

    dr = ReportDateRange(start_date=start_date, end_date=end_date)
    feature = _feature_filter()
    report_data = _get_report_data_cached(
        user_id=current_user.user_id,
        report_type="custom",
        dr=dr,
        feature_filter=feature,
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

    feature = _feature_filter()
    report_data = _get_report_data_cached(
        user_id=current_user.user_id,
        report_type=report_type,
        dr=dr,
        feature_filter=feature,
    )

    pdf_cache_key = _report_cache_key(
        user_id=current_user.user_id,
        report_type=f"pdf:{report_type}",
        dr=dr,
        feature_filter=feature,
    )

    cached_pdf = _cache_get(_PDF_CACHE, pdf_cache_key)
    if cached_pdf is not None:
        pdf_bytes = cached_pdf
    else:
        try:
            pdf_bytes = generate_report_pdf(report_data)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 500
        _cache_set(_PDF_CACHE, pdf_cache_key, pdf_bytes)

    file_name = f"phms_{report_type}_report_{dr.start_date.isoformat()}_{dr.end_date.isoformat()}.pdf"
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=file_name,
    )


@login_required
def health_records_api():
    """Return paginated health records (JSON) for the current user and date range.

    Query params:
        start_date, end_date (YYYY-MM-DD) - required
        page (int) - default 1
        per_page (int) - default 25
    """
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))
    if not start_date or not end_date:
        return jsonify({"error": "start_date and end_date are required (YYYY-MM-DD)"}), 400
    if start_date > end_date:
        return jsonify({"error": "start_date cannot be greater than end_date"}), 400

    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    try:
        per_page = int(request.args.get("per_page", 25))
    except ValueError:
        per_page = 25

    dr = ReportDateRange(start_date=start_date, end_date=end_date)
    items, total = ReportRepository.get_health_records_for_range_paginated(
        user_id=current_user.user_id,
        start_dt=dr.start_dt,
        end_dt=dr.end_dt,
        page=page,
        per_page=per_page,
    )

    def _serialize(item):
        return {
            "entry_id": getattr(item, "entry_id", None),
            "recorded_at": getattr(item, "recorded_at", None).isoformat() if getattr(item, "recorded_at", None) else None,
            "heart_rate": getattr(item, "heart_rate", None),
            "blood_pressure": getattr(item, "blood_pressure", None),
            "sugar": getattr(item, "sugar", None),
            "temperature": getattr(item, "temperature", None),
            "steps": getattr(item, "steps", None),
            "sleep_hours": getattr(item, "sleep_hours", None),
            "health_score": getattr(item, "health_score", None),
            "ml_regression_health_score": getattr(item, "ml_regression_health_score", None),
            "ml_classifier_risk_label": getattr(item, "ml_classifier_risk_label", None),
            "data_source": getattr(item, "data_source", None),
        }

    return jsonify({
        "total": int(total),
        "page": int(page),
        "per_page": int(per_page),
        "items": [_serialize(i) for i in items],
    })


@login_required
def report_charts_api():
    """Return lightweight chart datasets for the report visualizations.

    Query params:
        report_type (weekly|monthly|yearly|custom) - required
        start_date, end_date (YYYY-MM-DD) - required when report_type=custom
        feature (string) - optional
    """
    report_type = (request.args.get("report_type") or "").lower()
    if report_type in {"weekly", "monthly", "yearly"}:
        dr = _resolve_period(report_type)
    elif report_type == "custom":
        start_date = _parse_date(request.args.get("start_date"))
        end_date = _parse_date(request.args.get("end_date"))
        if not start_date or not end_date:
            return jsonify({"error": "start_date and end_date are required for custom charts"}), 400
        if start_date > end_date:
            return jsonify({"error": "start_date cannot be greater than end_date"}), 400
        dr = ReportDateRange(start_date=start_date, end_date=end_date)
    else:
        return jsonify({"error": "Invalid report type"}), 400

    feature = _feature_filter()
    report_data = _get_report_data_cached(
        user_id=current_user.user_id,
        report_type=report_type,
        dr=dr,
        feature_filter=feature,
    )

    payload = {
        "risk_indicators": report_data.get("risk_indicators", {}),
        "trend_analysis": report_data.get("trend_analysis", {}),
        "medication_adherence": report_data.get("medication_adherence", {}),
        "ml_classifier_distribution": report_data.get("ml_classifier_distribution", {}),
        "timeseries_trends": report_data.get("timeseries_trends", {}),
    }

    return jsonify(payload)
