"""Background job callbacks for notification dispatch workflows.

Jobs in this module delegate to service-layer logic only.
"""

from services.medication_log_service import MedicationLogManager


def push_due_notifications():
    """Dispatch scheduled in-app medication notifications."""
    return MedicationLogManager.schedule_notifications()
