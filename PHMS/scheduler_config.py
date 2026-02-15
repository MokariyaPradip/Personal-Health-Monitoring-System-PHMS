"""
Medication Log Scheduler Configuration

This module sets up the scheduled tasks for automatic medication log management:
1. Daily log creation (runs at midnight)
2. Notification scheduling (runs every minute)
3. Grace period checking (runs every minute)
4. Consecutive missed checking (runs daily at 11:59 PM)

To integrate with your Flask app, add this to your main app.py or a separate scheduler setup file:

from apscheduler.schedulers.background import BackgroundScheduler
from pytz import UTC
import logging

def setup_medication_scheduler(app):
    '''Setup APScheduler for medication log management'''
    
    scheduler = BackgroundScheduler(timezone=UTC)
    
    # Import the manager class
    from controllers.medication_log_controller import MedicationLogManager
    
    logger = logging.getLogger(__name__)
    
    # 1. Create daily logs at 00:00 (midnight)
    scheduler.add_job(
        func=MedicationLogManager.create_daily_logs,
        trigger='cron',
        hour=0,
        minute=0,
        id='create_daily_logs',
        name='Create daily medication logs',
        replace_existing=True
    )
    logger.info("Scheduled: Create daily logs at 00:00")
    
    # 2. Schedule notifications every minute
    scheduler.add_job(
        func=MedicationLogManager.schedule_notifications,
        trigger='interval',
        minutes=1,
        id='schedule_notifications',
        name='Schedule medication notifications',
        replace_existing=True,
        max_instances=1
    )
    logger.info("Scheduled: Send notifications every minute")
    
    # 3. Check grace period every minute
    scheduler.add_job(
        func=MedicationLogManager.check_grace_period_and_mark_missed,
        trigger='interval',
        minutes=1,
        id='check_grace_period',
        name='Check grace period and mark missed',
        replace_existing=True,
        max_instances=1
    )
    logger.info("Scheduled: Check grace period every minute")
    
    # 4. Check consecutive missed at 23:59 (11:59 PM)
    scheduler.add_job(
        func=MedicationLogManager.check_consecutive_missed_and_email,
        trigger='cron',
        hour=23,
        minute=59,
        id='check_consecutive_missed',
        name='Check consecutive missed and send email',
        replace_existing=True
    )
    logger.info("Scheduled: Check consecutive missed at 23:59")
    
    scheduler.start()
    logger.info("Medication scheduler started successfully!")
    
    return scheduler


# Alternative: Using APScheduler with Flask-APScheduler extension
from flask_apscheduler import APScheduler

SCHEDULER_CONFIG = {
    'SCHEDULER_API_ENABLED': True,
    'SCHEDULER_ENDPOINT_PREFIX': '/scheduler',
    'JOBS': [
        {
            'id': 'create_daily_logs',
            'func': 'controllers.medication_log_controller:MedicationLogManager.create_daily_logs',
            'trigger': 'cron',
            'args': (),
            'hour': 0,
            'minute': 0
        },
        {
            'id': 'schedule_notifications',
            'func': 'controllers.medication_log_controller:MedicationLogManager.schedule_notifications',
            'trigger': 'interval',
            'minutes': 1,
            'args': ()
        },
        {
            'id': 'check_grace_period',
            'func': 'controllers.medication_log_controller:MedicationLogManager.check_grace_period_and_mark_missed',
            'trigger': 'interval',
            'minutes': 1,
            'args': ()
        },
        {
            'id': 'check_consecutive_missed',
            'func': 'controllers.medication_log_controller:MedicationLogManager.check_consecutive_missed_and_email',
            'trigger': 'cron',
            'hour': 23,
            'minute': 59,
            'args': ()
        }
    ]
}
"""

import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SchedulerSetup:
    """Helper class for setting up medication scheduler"""
    
    _scheduler: Optional[object] = None
    
    @classmethod
    def setup_apscheduler(cls, app):
        """
        Setup APScheduler with medication log jobs
        
        Usage in app.py:
            scheduler = SchedulerSetup.setup_apscheduler(app)
        """
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from pytz import UTC
            from controllers.medication_log_controller import MedicationLogManager
            
            scheduler = BackgroundScheduler(timezone=UTC)
            
            # ============ WRAPPER FUNCTIONS WITH APP CONTEXT ============
            def job_create_daily_logs():
                with app.app_context():
                    return MedicationLogManager.create_daily_logs()
            
            def job_schedule_notifications():
                with app.app_context():
                    return MedicationLogManager.schedule_notifications()
            
            def job_check_grace_period():
                with app.app_context():
                    return MedicationLogManager.check_grace_period_and_mark_missed()
            
            def job_check_consecutive_missed():
                with app.app_context():
                    return MedicationLogManager.check_consecutive_missed_and_email()
            
            # Create daily logs at 00:00 (midnight)
            scheduler.add_job(
                func=job_create_daily_logs,
                trigger='cron',
                hour=0,
                minute=0,
                id='create_daily_logs',
                name='Create daily medication logs',
                replace_existing=True
            )
            logger.info("✓ Scheduled: Create daily logs at 00:00")
            
            # Schedule notifications every minute
            scheduler.add_job(
                func=job_schedule_notifications,
                trigger='interval',
                minutes=1,
                id='schedule_notifications',
                name='Schedule medication notifications',
                replace_existing=True,
                max_instances=1,
                misfire_grace_time=10,  # Allow 10 seconds grace for late starts
                coalesce=True  # Merge multiple pending executions into one
            )
            logger.info("✓ Scheduled: Send notifications every minute")
            
            # Check grace period every minute
            scheduler.add_job(
                func=job_check_grace_period,
                trigger='interval',
                minutes=1,
                id='check_grace_period',
                name='Check grace period and mark missed',
                replace_existing=True,
                max_instances=1,
                misfire_grace_time=10,  # Allow 10 seconds grace for late starts
                coalesce=True  # Merge multiple pending executions into one
            )
            logger.info("✓ Scheduled: Check grace period every minute")
            
            # Check consecutive missed at 23:59 (11:59 PM)
            scheduler.add_job(
                func=job_check_consecutive_missed,
                trigger='cron',
                hour=23,
                minute=59,
                id='check_consecutive_missed',
                name='Check consecutive missed and send email',
                replace_existing=True
            )
            logger.info("✓ Scheduled: Check consecutive missed at 23:59")
            
            scheduler.start()
            cls._scheduler = scheduler
            logger.info("━" * 50)
            logger.info("✓ Medication scheduler started successfully!")
            logger.info("━" * 50)
            
            return scheduler
            
        except ImportError as e:
            logger.error(f"APScheduler not installed: {str(e)}")
            logger.info("Install with: pip install APScheduler")
            return None
        except Exception as e:
            logger.error(f"Error setting up scheduler: {str(e)}")
            return None
    
    @classmethod
    def setup_flask_apscheduler(cls, app):
        """
        Setup Flask-APScheduler extension
        
        Usage in app.py:
            from flask_apscheduler import APScheduler
            scheduler = SchedulerSetup.setup_flask_apscheduler(app)
        """
        try:
            from flask_apscheduler import APScheduler
            from controllers.medication_log_controller import MedicationLogManager
            
            # Configure jobs
            app.config['SCHEDULER_JOBS'] = [
                {
                    'id': 'create_daily_logs',
                    'func': MedicationLogManager.create_daily_logs,
                    'trigger': 'cron',
                    'hour': 0,
                    'minute': 0
                },
                {
                    'id': 'schedule_notifications',
                    'func': MedicationLogManager.schedule_notifications,
                    'trigger': 'interval',
                    'minutes': 1
                },
                {
                    'id': 'check_grace_period',
                    'func': MedicationLogManager.check_grace_period_and_mark_missed,
                    'trigger': 'interval',
                    'minutes': 1
                },
                {
                    'id': 'check_consecutive_missed',
                    'func': MedicationLogManager.check_consecutive_missed_and_email,
                    'trigger': 'cron',
                    'hour': 23,
                    'minute': 59
                }
            ]
            
            app.config['SCHEDULER_API_ENABLED'] = True
            
            scheduler = APScheduler()
            scheduler.init_app(app)
            scheduler.start()
            
            logger.info("✓ Flask-APScheduler initialized successfully!")
            return scheduler
            
        except ImportError:
            logger.error("Flask-APScheduler not installed")
            logger.info("Install with: pip install Flask-APScheduler")
            return None
        except Exception as e:
            logger.error(f"Error setting up Flask-APScheduler: {str(e)}")
            return None
    
    @classmethod
    def get_scheduler(cls):
        """Get the current scheduler instance"""
        return cls._scheduler


# ============ CRON JOB CONFIGURATION FOR LINUX/UNIX SYSTEMS ============

"""
# Add to crontab using: crontab -e

# 1. Create daily logs at midnight (00:00)
0 0 * * * /usr/bin/curl -X POST http://localhost:5000/medication-log/create-daily

# 2. Schedule notifications every minute
* * * * * /usr/bin/curl -X POST http://localhost:5000/medication-log/send-notifications

# 3. Check grace period every minute
* * * * * /usr/bin/curl -X POST http://localhost:5000/medication-log/check-grace-period

# 4. Check consecutive missed at 23:59 (11:59 PM)
59 23 * * * /usr/bin/curl -X POST http://localhost:5000/medication-log/check-consecutive-missed

Alternative using celery (if you're using Celery for task queue):

from celery import Celery
celery = Celery(__name__)

@celery.task
def create_daily_logs_task():
    from controllers.medication_log_controller import MedicationLogManager
    return MedicationLogManager.create_daily_logs()

@celery.task
def schedule_notifications_task():
    from controllers.medication_log_controller import MedicationLogManager
    return MedicationLogManager.schedule_notifications()

@celery.task
def check_grace_period_task():
    from controllers.medication_log_controller import MedicationLogManager
    return MedicationLogManager.check_grace_period_and_mark_missed()

@celery.task
def check_consecutive_missed_task():
    from controllers.medication_log_controller import MedicationLogManager
    return MedicationLogManager.check_consecutive_missed_and_email()

# Configure beat schedule
from celery.schedules import crontab

celery.conf.beat_schedule = {
    'create-daily-logs': {
        'task': 'tasks.create_daily_logs_task',
        'schedule': crontab(hour=0, minute=0),
    },
    'schedule-notifications': {
        'task': 'tasks.schedule_notifications_task',
        'schedule': crontab(),  # Every minute
    },
    'check-grace-period': {
        'task': 'tasks.check_grace_period_task',
        'schedule': crontab(),  # Every minute
    },
    'check-consecutive-missed': {
        'task': 'tasks.check_consecutive_missed_task',
        'schedule': crontab(hour=23, minute=59),
    }
}
"""
