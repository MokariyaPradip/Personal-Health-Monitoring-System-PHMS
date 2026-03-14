from .email_workflows import MedicationLogEmailMixin
from .scheduler_workflows import MedicationLogSchedulerMixin
from .reporting_workflows import MedicationLogReportingMixin
from . import email_workflows, scheduler_workflows


class MedicationLogManager(MedicationLogEmailMixin, MedicationLogSchedulerMixin, MedicationLogReportingMixin):
    """Manager class for medication log operations."""

    # Maximum grace period is 30 minutes
    # Actual grace period = min(30 minutes, time_gap_between_doses)
    # For high-frequency meds, grace period is shorter to avoid overlapping with next dose
    MIN_GRACE_PERIOD_MINUTES = 30
    CONSECUTIVE_MISSED_THRESHOLD = 2
    EMAIL_SEND_MAX_ATTEMPTS = 2  # First attempt + one retry


# Bind class reference for static methods that refer to MedicationLogManager.
email_workflows.MedicationLogManager = MedicationLogManager
scheduler_workflows.MedicationLogManager = MedicationLogManager
