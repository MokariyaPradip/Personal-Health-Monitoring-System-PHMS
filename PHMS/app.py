"""PHMS Main Application Entry Point.

Personal Health Monitoring System (PHMS) - Flask Application Launcher

This module serves as the main entry point for the PHMS web application.
It initializes the Flask app, registers routes, sets up the medication
scheduler, and provides CLI commands for medication log management.

Components Initialized:
    - Flask application (via create_app factory)
    - Database models and migrations
    - URL routes and blueprints
    - APScheduler for medication reminders
    - Medication log system

Application Flow:
    1. Create Flask app instance with configuration
    2. Register all application routes
    3. Initialize medication logs for today
    4. Start background scheduler for automated tasks
    5. Launch development server

Scheduler Jobs:
    - Daily log creation (midnight): Creates medication logs for all active meds
    - Notification scheduling (every minute): Sends medication reminders
    - Grace period checking (every minute): Marks overdue medications as missed
    - Consecutive missed detection is evaluated during grace-period checks

CLI Commands:
    - flask create-initial-logs: Manually trigger daily log creation

Environment Variables:
    - FLASK_DEBUG: Enable debug mode (0=off, 1=on)
    - DATABASE_URL: Database connection string (defaults to SQLite)
    - MAIL_SERVER: SMTP server for email notifications

Usage:
    Development Server:
        $ python app.py
    
    Production Server (using Gunicorn):
        Option 1 - Separate scheduler process (RECOMMENDED):
            Terminal 1: $ ENABLE_SCHEDULER=1 python app.py  # Dedicated scheduler
            Terminal 2: $ gunicorn -w 4 -b 0.0.0.0:5000 app:app  # Web workers
        
        Option 2 - Single worker with scheduler:
            $ gunicorn -w 1 -e ENABLE_SCHEDULER=1 -b 0.0.0.0:5000 app:app
        
        Option 3 - Systemd service (Linux):
            # Create separate services for web and scheduler
            # See deployment documentation for details
    
    CLI Commands:
        $ flask create-initial-logs

Server Access:
    - Local: http://127.0.0.1:5000
    - Network: http://<your-ip>:5000

Note:
    - Debug mode auto-reloads on code changes
    - Scheduler runs in single-instance mode to prevent duplicate jobs
    - Set ENABLE_SCHEDULER=1 to explicitly enable scheduler in production
    - Database migrations run automatically on first start
    - Medication logs and scheduler start only via explicit runtime bootstrap
      (importing this module does not start background services)
"""

import os
import sys
from config import create_app
import models  # noqa: F401 (needed for migrations)
from routes import register_routes

app = create_app()

register_routes(app)

# ============ INITIALIZE SCHEDULER ============
def init_scheduler():
    """Initialize the APScheduler for automated medication management.
    
    Sets up background scheduler with three automated tasks:
    1. Daily log creation at midnight (00:00)
    2. Medication reminders every minute
    3. Grace period expiration checking every minute
    
    Returns:
        BackgroundScheduler | None: Scheduler instance if successful, None on error
    
    Scheduler Jobs:
        - create_daily_logs: Creates medication logs for all active medications
        - schedule_notifications: Sends medication intake reminders
        - check_grace_period: Marks medications as missed after grace period
    
    Configuration:
        - Timezone: Device local timezone
        - Max instances: 1 per job (prevents overlapping executions)
        - Misfire grace time: 10 seconds
        - Coalesce: Enabled (merges missed executions)
    
    Example:
        >>> scheduler = init_scheduler()
        ✓ Scheduled: Create daily logs at 00:00
        ✓ Scheduled: Send notifications every minute
        ✓ Scheduled: Check grace period every minute
        ✓ Medication scheduler started successfully!
    
    Error Handling:
        - Returns None if APScheduler not installed
        - Returns None if initialization fails
        - Prints error message with emoji indicator
    
    Note:
        - Called automatically during app startup
        - Runs in background (non-blocking)
        - Requires app context for database operations
        - Jobs wrapped with app.app_context() for proper execution
    """
    try:
        from scheduler_config import SchedulerSetup
        scheduler = SchedulerSetup.setup_apscheduler(app)
        return scheduler
    except Exception as e:
        print(f"❌ Error initializing scheduler: {str(e)}")
        return None

def init_medication_logs():
    """Initialize medication logs for today's schedule at application startup.
    
    Creates medication log entries for all active medications with today's date
    and their scheduled intake times. Handles existing logs gracefully by skipping
    duplicates.
    
    Returns:
        dict | None: Result dictionary with status and statistics, None on error
            - status (str): 'success' or 'error'
            - created (int): Number of logs created
            - skipped (int): Number of medications already logged
            - total_medications (int): Total active medications processed
    
    Initialization Logic:
        1. Fetch all active medications (is_active() == True)
        2. For each medication, get scheduled times from frequency
        3. Check if logs already exist for today
        4. Create pending logs for upcoming scheduled times
        5. Mark overdue pending logs as skipped (past dates + today's passed times)
    
    Example Result:
        {
            'status': 'success',
            'created': 12,
            'skipped': 3,
            'total_medications': 5
        }
    
    Use Cases:
        - Application startup: Ensures today's logs exist
        - Server restart: Re-initializes without duplicating
        - Missed startup: Creates logs for remaining doses
    
    Error Handling:
        - Returns None if MedicationLogManager import fails
        - Returns None if initialization raises exception
        - Prints error message with details
    
    Note:
        - Called automatically at app startup (before scheduler starts)
        - Idempotent operation (safe to call multiple times)
        - Only creates logs for active medications
        - Respects medication start_date and end_date
        - Past pending logs automatically marked as 'skipped'
    """
    try:
        from services.medication_log_service import MedicationLogManager
        result = MedicationLogManager.initialize_medication_logs()
        return result
    except Exception as e:
        print(f"❌ Error initializing medication logs: {str(e)}")
        return None

# ============ SCHEDULER INITIALIZATION ============
# Only initialize scheduler if explicitly enabled to prevent duplicate execution
# in multi-worker environments (Gunicorn, uWSGI, etc.)
#
# For production deployment:
#   Option 1: Run scheduler in a separate dedicated process
#     $ ENABLE_SCHEDULER=1 python app.py  # Scheduler process only
#     $ gunicorn -w 4 app:app              # Web workers without scheduler
#
#   Option 2: Enable scheduler in single worker/process
#     $ gunicorn -w 1 -e ENABLE_SCHEDULER=1 app:app
#
# For development (single process):
#     $ python app.py  # Scheduler starts automatically

scheduler = None

def should_start_scheduler():
    """Determine if scheduler should start in this process.
    
    Scheduler starts only when:
    1. ENABLE_SCHEDULER=1 is explicitly set (production multi-worker), OR
    2. Running directly via 'python app.py' (development single-process)
    3. NOT running via WSGI server without explicit enable flag
    
    Returns:
        bool: True if scheduler should start, False otherwise
    """
    # Check for explicit enable flag (production)
    enable_scheduler = os.environ.get('ENABLE_SCHEDULER', '').lower() in ('1', 'true', 'yes')
    if enable_scheduler:
        return True
    
    # Detect if running under WSGI server (Gunicorn, uWSGI, etc.)
    # These servers set specific environment variables
    wsgi_indicators = [
        'gunicorn',  # Gunicorn process
        'uwsgi',     # uWSGI process
        'mod_wsgi',  # Apache mod_wsgi
    ]
    
    # Check if running under WSGI server by examining process and environment
    server_software = os.environ.get('SERVER_SOFTWARE', '').lower()
    for indicator in wsgi_indicators:
        if indicator in server_software or indicator in sys.argv[0].lower():
            # Running under WSGI server without explicit enable - don't start
            return False
    
    # Default: start scheduler (development mode via 'python app.py')
    return True

def bootstrap_background_services(start_scheduler=None, initialize_logs=True):
    """Explicitly initialize startup/background services for this process.

    This function is intentionally NOT called at import time. Call it from
    explicit runtime entrypoints only (for example `if __name__ == '__main__'`).

    Args:
        start_scheduler (bool | None):
            - None: follow should_start_scheduler() policy
            - True: force scheduler start in this process
            - False: keep scheduler disabled in this process
        initialize_logs (bool): whether to run startup medication log initialization

    Returns:
        dict: startup status details
    """
    global scheduler

    scheduler_enabled = should_start_scheduler() if start_scheduler is None else bool(start_scheduler)
    startup_status = {
        'initialize_logs_requested': initialize_logs,
        'scheduler_enabled': scheduler_enabled,
        'logs_initialized': False,
        'scheduler_started': False,
        'init_result': None,
    }

    with app.app_context():
        if initialize_logs:
            print("\n🔄 Initializing medication logs...")
            init_result = init_medication_logs()
            startup_status['init_result'] = init_result
            if init_result and init_result.get('status') == 'success':
                startup_status['logs_initialized'] = True
                print("✅ Medication logs initialized successfully")

        if scheduler_enabled:
            if scheduler is not None:
                startup_status['scheduler_started'] = True
                print("✅ Scheduler already started in this process")
            else:
                print("\n🚀 Starting scheduler...")
                scheduler = init_scheduler()
                startup_status['scheduler_started'] = scheduler is not None
                if scheduler:
                    print("✅ Scheduler started successfully (single instance mode)")
        else:
            print("⏸️  Scheduler disabled in this process (set ENABLE_SCHEDULER=1 to enable)")

    return startup_status

# ============ CLI COMMANDS ============
@app.cli.command('create-initial-logs')
def create_initial_logs():
    """Flask CLI command to manually create medication logs for all active medications.
    
    Creates daily medication log entries for all active medications in the system.
    Useful for manual triggering, testing, or recovery from scheduler failures.
    
    Usage:
        $ flask create-initial-logs
    
    Output Information:
        - Number of logs created
        - Total active medications processed
        - Number of medications skipped (already have logs)
    
    Example Output:
        $ flask create-initial-logs
        📋 Creating initial medication logs for all active medications...
        ✅ Success!
           - Created: 15 logs
           - Total active medications: 5
           - Skipped: 2
    
    Use Cases:
        1. Manual Recovery: If scheduler failed to create daily logs
        2. Testing: Verify medication log creation works correctly
        3. Debugging: Check which medications are active
        4. Initial Setup: Create first batch of logs after adding medications
    
    Behavior:
        - Queries all medications and filters by is_active()
        - Creates logs for each scheduled time defined by frequency
        - Skips creation if logs already exist for today
        - Commits all changes to database
    
    Error Handling:
        - Displays error message if MedicationLogManager import fails
        - Shows warning if result status is not 'success'
        - Prints exception details for debugging
    
    Note:
        - Requires Flask app context (provided by @app.cli.command)
        - Safe to run multiple times (idempotent)
        - Does not send notifications (only creates logs)
        - Scheduler will still run its own daily job at midnight
    """
    with app.app_context():
        try:
            from services.medication_log_service import MedicationLogManager
            
            print("📋 Creating initial medication logs for all active medications...")
            result = MedicationLogManager.create_daily_logs()
            
            if result.get('status') == 'success':
                print(f"✅ Success!")
                print(f"   - Created: {result.get('created', 0)} logs")
                print(f"   - Total active medications: {result.get('total_medications', 0)}")
                print(f"   - Skipped: {result.get('skipped', 0)}")
            else:
                print(f"⚠️ {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ Error creating logs: {str(e)}")

if __name__ == '__main__':
    # Explicit one-time startup wiring for local/dev or dedicated scheduler process.
    bootstrap_background_services()

    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug_mode)
