from flask import Blueprint

from controllers import reports_controller


reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("", methods=["GET"])
def reports_home():
    return reports_controller.reports_home()


@reports_bp.route("/weekly", methods=["GET"])
def weekly_report():
    return reports_controller.weekly_report()


@reports_bp.route("/monthly", methods=["GET"])
def monthly_report():
    return reports_controller.monthly_report()


@reports_bp.route("/yearly", methods=["GET"])
def yearly_report():
    return reports_controller.yearly_report()


@reports_bp.route("/custom", methods=["GET"])
def custom_report():
    return reports_controller.custom_report()


@reports_bp.route("/records", methods=["GET"])
def health_records():
    return reports_controller.health_records_api()


@reports_bp.route("/charts", methods=["GET"])
def report_charts():
    return reports_controller.report_charts_api()


@reports_bp.route("/<string:report_type>/pdf", methods=["GET"])
def report_pdf(report_type):
    return reports_controller.report_pdf(report_type)


def register_reports_routes(app):
    """Register reports blueprint routes."""
    app.register_blueprint(reports_bp)
