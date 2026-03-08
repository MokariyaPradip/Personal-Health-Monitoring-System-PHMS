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
    - Consecutive missed checking (11:59 PM): Sends email alerts for patterns

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
        $ gunicorn -w 4 -b 0.0.0.0:5000 app:app
    
    CLI Commands:
        $ flask create-initial-logs

Server Access:
    - Local: http://127.0.0.1:5000
    - Network: http://<your-ip>:5000

Note:
    - Debug mode auto-reloads on code changes
    - Scheduler starts automatically in app context
    - Database migrations run automatically on first start
    - Medication logs initialized at startup for today's schedule
"""

import os
from config import create_app, db
from models import *   # noqa: F401 (needed for migrations)
from routes import register_routes
import click

app = create_app()

register_routes(app)

# ============ INITIALIZE SCHEDULER ============
def init_scheduler():
    """Initialize the APScheduler for automated medication management.
    
    Sets up background scheduler with four automated tasks:
    1. Daily log creation at midnight (00:00)
    2. Medication reminders every minute
    3. Grace period expiration checking every minute
    4. Consecutive missed alert checking at 11:59 PM
    
    Returns:
        BackgroundScheduler | None: Scheduler instance if successful, None on error
    
    Scheduler Jobs:
        - create_daily_logs: Creates medication logs for all active medications
        - schedule_notifications: Sends medication intake reminders
        - check_grace_period: Marks medications as missed after grace period
        - check_consecutive_missed: Emails users about missed dose patterns
    
    Configuration:
        - Timezone: UTC
        - Max instances: 1 per job (prevents overlapping executions)
        - Misfire grace time: 10 seconds
        - Coalesce: Enabled (merges missed executions)
    
    Example:
        >>> scheduler = init_scheduler()
        ✓ Scheduled: Create daily logs at 00:00
        ✓ Scheduled: Send notifications every minute
        ✓ Scheduled: Check grace period every minute
        ✓ Scheduled: Check consecutive missed at 23:59
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
        5. Mark past pending logs as missed (if grace period expired)
    
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
        from controllers.medication_log_controller import MedicationLogManager
        result = MedicationLogManager.initialize_medication_logs()
        return result
    except Exception as e:
        print(f"❌ Error initializing medication logs: {str(e)}")
        return None

# Start scheduler and initialize logs when app context exists
with app.app_context():
    # Initialize medication logs first (create/verify logs)
    print("\n🔄 Initializing medication logs...")
    init_result = init_medication_logs()
    if init_result and init_result.get('status') == 'success':
        print(f"✅ Medication logs initialized successfully")
    
    # Then start the scheduler
    print("\n🚀 Starting scheduler...")
    scheduler = init_scheduler()

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
            from controllers.medication_log_controller import MedicationLogManager
            
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
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug_mode)
