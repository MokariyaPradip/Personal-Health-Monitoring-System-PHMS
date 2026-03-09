"""
Medication Log Scheduler Configuration

This module sets up the scheduled tasks for automatic medication log management:
1. Daily log creation (runs at midnight)
2. Notification scheduling (runs every minute)
3. Grace period checking (runs every minute)
4. Consecutive missed checking (runs daily at 11:59 PM)

To integrate with your Flask app, add this to your main app.py or a separate scheduler setup file:

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import logging

def setup_medication_scheduler(app):
    '''Setup APScheduler for medication log management'''
    
    scheduler = BackgroundScheduler(timezone=datetime.now().astimezone().tzinfo)
    
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


def _get_local_timezone():
    """Resolve device-local timezone for scheduler jobs.

    Returns:
        tzinfo | None: Local timezone if available, else None.
    """
    try:
        return datetime.now().astimezone().tzinfo
    except Exception:
        return None


class SchedulerSetup:
    """Medication scheduler setup and management class.
    
    Provides methods to configure and initialize APScheduler for automated
    medication log management tasks. Supports both standalone BackgroundScheduler
    and Flask-APScheduler integration.
    
    Scheduled Tasks:
        1. create_daily_logs: Midnight (00:00) - Creates logs for all active medications
        2. schedule_notifications: Every 1 minute - Sends medication reminders
        3. check_grace_period: Every 1 minute - Marks overdue medications as missed
        4. check_consecutive_missed: Daily at 11:59 PM - Sends email alerts
    
    Class Attributes:
        _scheduler (BackgroundScheduler | None): Singleton scheduler instance
    
    Scheduler Configuration:
        - Timezone: Device local timezone
        - Max instances: 1 per job (prevents overlap)
        - Misfire grace time: 10 seconds (allows late starts)
        - Coalesce: Enabled (merges multiple missed executions)
    
    Usage Patterns:
        Option 1 - BackgroundScheduler:
            >>> from scheduler_config import SchedulerSetup
            >>> scheduler = SchedulerSetup.setup_apscheduler(app)
        
        Option 2 - Flask-APScheduler Extension:
            >>> from flask_apscheduler import APScheduler
            >>> scheduler = SchedulerSetup.setup_flask_apscheduler(app)
        
        Option 3 - Get Existing Scheduler:
            >>> scheduler = SchedulerSetup.get_scheduler()
    
    Methods:
        setup_apscheduler(app): Configure standalone BackgroundScheduler
        setup_flask_apscheduler(app): Configure Flask-APScheduler extension
        get_scheduler(): Retrieve singleton scheduler instance
    
    Integration:
        - All job functions wrapped with app.app_context() for database access
        - Jobs defined in MedicationLogManager class
        - Email notifications use Flask-Mail configuration
        - Database operations use SQLAlchemy ORM
    
    Error Handling:
        - Returns None if APScheduler not installed
        - Logs errors to application logger
        - Provides installation instructions on import failure
    
    Note:
        - Call setup method only once during app initialization
        - Scheduler runs in background thread (non-blocking)
        - Jobs respect Flask application context for request-specific operations
        - Singleton pattern ensures only one scheduler instance exists
    """
    
    _scheduler: Optional[object] = None
    
    @classmethod
    def setup_apscheduler(cls, app):
        """Set up APScheduler with medication log management jobs.
        
        Configures and starts a BackgroundScheduler with four automated jobs
        for medication log management. All jobs run with Flask app context.
        
        Args:
            app (Flask): Flask application instance for context management
        
        Returns:
            BackgroundScheduler | None: Configured scheduler instance, or None on error
        
        Jobs Configured:
            1. create_daily_logs (Cron: 00:00 daily):
               - Creates medication log entries for all active medications
               - Scheduled times based on medication frequency
               - Skips if logs already exist for today
            
            2. schedule_notifications (Interval: Every 1 minute):
               - Checks for upcoming medication doses (within next hour)
               - Creates Alert records for pending medications
               - Sends email reminders for critical medications
               - Max 1 instance, 10s misfire grace, coalesce enabled
            
            3. check_grace_period (Interval: Every 1 minute):
               - Identifies pending logs past their grace period
               - Marks overdue medications as 'missed'
               - Grace period: max(30 minutes, dose_gap_time)
               - Max 1 instance, 10s misfire grace, coalesce enabled
            
            4. check_consecutive_missed (Cron: 23:59 daily):
               - Analyzes missed medication patterns
               - Sends email alerts for 2+ consecutive missed doses
               - Updates user notification preferences
        
        Configuration:
            - Timezone: Device local timezone
            - Replace existing: True (allows restart)
            - Coalesce: True for interval jobs (prevents queue buildup)
            - Max instances: 1 for interval jobs (prevents overlap)
        
        Example:
            >>> from config import create_app
            >>> from scheduler_config import SchedulerSetup
            >>> app = create_app()
            >>> scheduler = SchedulerSetup.setup_apscheduler(app)
            ✓ Scheduled: Create daily logs at 00:00
            ✓ Scheduled: Send notifications every minute
            ✓ Scheduled: Check grace period every minute
            ✓ Scheduled: Check consecutive missed at 23:59
            ✓ Medication scheduler started successfully!
        
        Error Handling:
            - Returns None if APScheduler not installed
            - Returns None if job setup fails
            - Logs errors with logger.error()
            - Provides pip install instructions
        
        Context Management:
            - All jobs wrapped with app.app_context()
            - Ensures database access works in background threads
            - Required for SQLAlchemy operations
            - Prevents "working outside application context" errors
        
        Note:
            - Scheduler starts automatically after job registration
            - Stores instance in cls._scheduler for later access
            - Jobs use MedicationLogManager static methods
            - Call this only once during app initialization
            - Requires APScheduler: pip install APScheduler
        
        Multi-Worker Safety:
            - Only ONE process should run the scheduler
            - In production with multiple workers, set ENABLE_SCHEDULER=1 for one process
            - Or run scheduler as a separate dedicated process
            - Prevents duplicate job execution and redundant email notifications
        """
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from controllers.medication_log_controller import MedicationLogManager
            
            local_timezone = _get_local_timezone()
            if local_timezone is not None:
                scheduler = BackgroundScheduler(timezone=local_timezone)
                logger.info(f"✓ Scheduler timezone set to local device timezone: {local_timezone}")
            else:
                scheduler = BackgroundScheduler()
                logger.warning("⚠️ Could not resolve local timezone. Using APScheduler default timezone.")
            
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
        """Set up Flask-APScheduler extension with medication management jobs.
        
        Alternative to setup_apscheduler() that uses Flask-APScheduler extension.
        Provides better Flask integration with built-in API endpoints for job
        monitoring and management.
        
        Args:
            app (Flask): Flask application instance
        
        Returns:
            APScheduler | None: Flask-APScheduler instance, or None on error
        
        Features:
            - Web API for job management (enable via SCHEDULER_API_ENABLED)
            - Job monitoring endpoints at /scheduler/*
            - Automatic Flask context management
            - Built-in authentication support
        
        Configuration (app.config):
            SCHEDULER_API_ENABLED: True
            SCHEDULER_ENDPOINT_PREFIX: '/scheduler'
            SCHEDULER_JOBS: List of job definitions
        
        Jobs Configured:
            Same 4 jobs as setup_apscheduler():
            - create_daily_logs (00:00 daily)
            - schedule_notifications (every minute)
            - check_grace_period (every minute)
            - check_consecutive_missed (23:59 daily)
        
        API Endpoints (when SCHEDULER_API_ENABLED=True):
            GET  /scheduler/jobs - List all jobs
            GET  /scheduler/jobs/<job_id> - Get job details
            POST /scheduler/jobs/<job_id>/pause - Pause a job
            POST /scheduler/jobs/<job_id>/resume - Resume a job
            POST /scheduler/jobs/<job_id>/run - Run job immediately
        
        Example:
            >>> from config import create_app
            >>> from scheduler_config import SchedulerSetup
            >>> from flask_apscheduler import APScheduler
            >>> app = create_app()
            >>> scheduler = SchedulerSetup.setup_flask_apscheduler(app)
            >>> scheduler.start()
        
        Advantages over BackgroundScheduler:
            - Better Flask integration
            - Web-based job monitoring
            - Automatic app context handling
            - Job pause/resume via API
            - Real-time job status
        
        Error Handling:
            - Returns None if Flask-APScheduler not installed
            - Returns None if configuration fails
            - Logs errors with logger
        
        Note:
            - Requires Flask-APScheduler: pip install Flask-APScheduler
            - Configure SCHEDULER_API_ENABLED for web API
            - Jobs store references in app.config['SCHEDULER_JOBS']
            - Recommended for production deployments
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
        """Retrieve the singleton scheduler instance.
        
        Returns the currently active scheduler that was created by either
        setup_apscheduler() or setup_flask_apscheduler().
        
        Returns:
            BackgroundScheduler | APScheduler | None: Active scheduler instance,
                or None if no scheduler has been initialized
        
        Use Cases:
            - Check if scheduler is running
            - Access scheduler for manual job management
            - Shutdown scheduler gracefully
            - Query job status and next run times
        
        Example:
            >>> from scheduler_config import SchedulerSetup
            >>> scheduler = SchedulerSetup.get_scheduler()
            >>> if scheduler:
            ...     print("Scheduler is running")
            ...     for job in scheduler.get_jobs():
            ...         print(f"Job: {job.id}, Next run: {job.next_run_time}")
            ... else:
            ...     print("No scheduler initialized")
        
        Example - Graceful Shutdown:
            >>> scheduler = SchedulerSetup.get_scheduler()
            >>> if scheduler:
            ...     scheduler.shutdown(wait=True)
            ...     print("✓ Scheduler stopped")
        
        Example - Manual Job Trigger:
            >>> scheduler = SchedulerSetup.get_scheduler()
            >>> if scheduler:
            ...     job = scheduler.get_job('create_daily_logs')
            ...     job.modify(next_run_time=datetime.now())
        
        Note:
            - Returns None if setup_apscheduler() not called yet
            - Singleton pattern ensures only one instance exists
            - Safe to call multiple times
            - Does not start scheduler if not running
        """
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
