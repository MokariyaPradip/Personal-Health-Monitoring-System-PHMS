"""Background job callbacks for medication-log workflows.

Jobs in this module delegate to service-layer logic only.
"""

from services.medication_log_service import MedicationLogManager


def create_daily_logs():
    """Create daily medication logs for active medications."""
    return MedicationLogManager.create_daily_logs()


def schedule_notifications():
    """Schedule due medication reminder notifications."""
    return MedicationLogManager.schedule_notifications()


def check_grace_period_and_mark_missed():
    """Mark overdue pending medication logs as missed."""
    return MedicationLogManager.check_grace_period_and_mark_missed()


def catch_up_overdue_pending_logs():
    """Run startup catch-up to mark overdue pending logs as skipped."""
    return MedicationLogManager.mark_past_pending_logs_as_skipped()
