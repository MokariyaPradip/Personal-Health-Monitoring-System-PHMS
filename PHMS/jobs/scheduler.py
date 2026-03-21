"""Scheduler orchestration for PHMS background jobs.

This module wires APScheduler/Flask-APScheduler jobs using callbacks from
the jobs layer. Job callbacks delegate to services only.
"""

import logging
from datetime import datetime
from typing import Optional

from jobs.medication_tasks import (
    create_daily_logs,
    check_grace_period_and_mark_missed,
    catch_up_overdue_pending_logs,
)
from jobs.notification_tasks import push_due_notifications
from jobs.smartwatch_tasks import sync_all_connected_smartwatches

logger = logging.getLogger(__name__)


def _get_local_timezone():
    """Resolve local timezone for scheduler execution."""
    try:
        return datetime.now().astimezone().tzinfo
    except Exception:
        return None


SCHEDULER_CONFIG = {
    'SCHEDULER_API_ENABLED': True,
    'SCHEDULER_ENDPOINT_PREFIX': '/scheduler',
    'JOBS': [
        {
            'id': 'create_daily_logs',
            'func': 'jobs.medication_tasks:create_daily_logs',
            'trigger': 'cron',
            'args': (),
            'hour': 0,
            'minute': 0,
        },
        {
            'id': 'schedule_notifications',
            'func': 'jobs.notification_tasks:push_due_notifications',
            'trigger': 'interval',
            'minutes': 1,
            'args': (),
        },
        {
            'id': 'check_grace_period',
            'func': 'jobs.medication_tasks:check_grace_period_and_mark_missed',
            'trigger': 'interval',
            'minutes': 1,
            'args': (),
        },
    ],
}


class SchedulerSetup:
    """Build and manage the PHMS scheduler instance."""

    _scheduler: Optional[object] = None

    @classmethod
    def setup_apscheduler(cls, app):
        """Configure BackgroundScheduler jobs from jobs/ callbacks."""
        try:
            from apscheduler.schedulers.background import BackgroundScheduler

            local_timezone = _get_local_timezone()
            if local_timezone is not None:
                scheduler = BackgroundScheduler(timezone=local_timezone)
                logger.info("✓ Scheduler timezone set to local device timezone: %s", local_timezone)
            else:
                scheduler = BackgroundScheduler()
                logger.warning("⚠️ Could not resolve local timezone. Using APScheduler default timezone.")

            # Wrap callbacks to ensure Flask app context during DB/service access.
            def job_create_daily_logs():
                with app.app_context():
                    return create_daily_logs()

            def job_push_due_notifications():
                with app.app_context():
                    return push_due_notifications()

            def job_check_grace_period():
                with app.app_context():
                    return check_grace_period_and_mark_missed()

            def job_sync_smartwatches():
                with app.app_context():
                    return sync_all_connected_smartwatches()

            smartwatch_sync_interval_hours = app.config.get('SMARTWATCH_SYNC_INTERVAL_HOURS', 6)
            smartwatch_sync_max_instances = app.config.get('SMARTWATCH_SYNC_MAX_INSTANCES', 1)
            smartwatch_sync_misfire_grace = app.config.get('SMARTWATCH_SYNC_MISFIRE_GRACE_SECONDS', 60)
            smartwatch_sync_coalesce = app.config.get('SMARTWATCH_SYNC_COALESCE', True)

            scheduler.add_job(
                func=job_create_daily_logs,
                trigger='cron',
                hour=0,
                minute=0,
                id='create_daily_logs',
                name='Create daily medication logs',
                replace_existing=True,
            )
            logger.info("✓ Scheduled: Create daily logs at 00:00")

            scheduler.add_job(
                func=job_push_due_notifications,
                trigger='interval',
                minutes=1,
                id='schedule_notifications',
                name='Schedule medication notifications',
                replace_existing=True,
                max_instances=1,
                misfire_grace_time=10,
                coalesce=True,
            )
            logger.info("✓ Scheduled: Send notifications every minute")

            scheduler.add_job(
                func=job_check_grace_period,
                trigger='interval',
                minutes=1,
                id='check_grace_period',
                name='Check grace period and mark missed',
                replace_existing=True,
                max_instances=1,
                misfire_grace_time=10,
                coalesce=True,
            )
            logger.info("✓ Scheduled: Check grace period every minute")

            scheduler.add_job(
                func=job_sync_smartwatches,
                trigger='interval',
                hours=smartwatch_sync_interval_hours,
                id='sync_all_smartwatches',
                name='Sync all connected smartwatch accounts',
                replace_existing=True,
                max_instances=smartwatch_sync_max_instances,
                misfire_grace_time=smartwatch_sync_misfire_grace,
                coalesce=smartwatch_sync_coalesce,
            )
            logger.info(
                "✓ Scheduled: Sync smartwatches every %s hour(s) (max_instances=%s, misfire_grace=%ss, coalesce=%s)",
                smartwatch_sync_interval_hours,
                smartwatch_sync_max_instances,
                smartwatch_sync_misfire_grace,
                smartwatch_sync_coalesce,
            )

            scheduler.start()
            cls._scheduler = scheduler

            with app.app_context():
                startup_skip_result = catch_up_overdue_pending_logs()

            if startup_skip_result.get('status') == 'success':
                logger.info(
                    "✓ Startup catch-up complete: skipped=%s (evaluated=%s)",
                    startup_skip_result.get('skipped', 0),
                    startup_skip_result.get('evaluated', 0),
                )
            else:
                logger.warning(
                    "⚠️ Startup catch-up failed: %s",
                    startup_skip_result.get('message', 'Unknown error'),
                )

            logger.info("✓ Medication scheduler started successfully!")
            return scheduler

        except ImportError as exc:
            logger.error("APScheduler not installed: %s", str(exc))
            logger.info("Install with: pip install APScheduler")
            return None
        except Exception as exc:
            logger.error("Error setting up scheduler: %s", str(exc))
            return None

    @classmethod
    def setup_flask_apscheduler(cls, app):
        """Configure Flask-APScheduler using jobs/ callbacks."""
        try:
            from flask_apscheduler import APScheduler

            def job_create_daily_logs():
                with app.app_context():
                    return create_daily_logs()

            def job_push_due_notifications():
                with app.app_context():
                    return push_due_notifications()

            def job_check_grace_period():
                with app.app_context():
                    return check_grace_period_and_mark_missed()

            app.config['SCHEDULER_JOBS'] = [
                {
                    'id': 'create_daily_logs',
                    'func': job_create_daily_logs,
                    'trigger': 'cron',
                    'hour': 0,
                    'minute': 0,
                },
                {
                    'id': 'schedule_notifications',
                    'func': job_push_due_notifications,
                    'trigger': 'interval',
                    'minutes': 1,
                },
                {
                    'id': 'check_grace_period',
                    'func': job_check_grace_period,
                    'trigger': 'interval',
                    'minutes': 1,
                },
            ]
            app.config['SCHEDULER_API_ENABLED'] = True

            scheduler = APScheduler()
            scheduler.init_app(app)
            scheduler.start()
            cls._scheduler = scheduler

            with app.app_context():
                startup_skip_result = catch_up_overdue_pending_logs()

            if startup_skip_result.get('status') == 'success':
                logger.info(
                    "✓ Startup catch-up complete: skipped=%s (evaluated=%s)",
                    startup_skip_result.get('skipped', 0),
                    startup_skip_result.get('evaluated', 0),
                )
            else:
                logger.warning(
                    "⚠️ Startup catch-up failed: %s",
                    startup_skip_result.get('message', 'Unknown error'),
                )

            logger.info("✓ Flask-APScheduler initialized successfully!")
            return scheduler

        except ImportError:
            logger.error("Flask-APScheduler not installed")
            logger.info("Install with: pip install Flask-APScheduler")
            return None
        except Exception as exc:
            logger.error("Error setting up Flask-APScheduler: %s", str(exc))
            return None

    @classmethod
    def get_scheduler(cls):
        """Return active scheduler instance if initialized."""
        return cls._scheduler
