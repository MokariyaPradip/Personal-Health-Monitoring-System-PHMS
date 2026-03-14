"""Thin scheduler bootstrap.

Backward-compatible import surface for scheduler setup symbols while the
implementation lives in jobs/scheduler.py.
"""

from jobs.scheduler import SchedulerSetup, SCHEDULER_CONFIG


def setup_medication_scheduler(app):
    """Compatibility wrapper for older startup paths."""
    return SchedulerSetup.setup_apscheduler(app)


__all__ = [
    'SchedulerSetup',
    'SCHEDULER_CONFIG',
    'setup_medication_scheduler',
]
