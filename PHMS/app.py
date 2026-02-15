import os
from config import create_app, db
from models import *   # noqa: F401 (needed for migrations)
from routes import register_routes
import click

app = create_app()

register_routes(app)

# ============ INITIALIZE SCHEDULER ============
def init_scheduler():
    """Initialize the medication log scheduler"""
    try:
        from scheduler_config import SchedulerSetup
        scheduler = SchedulerSetup.setup_apscheduler(app)
        return scheduler
    except Exception as e:
        print(f"❌ Error initializing scheduler: {str(e)}")
        return None

def init_medication_logs():
    """Initialize medication logs on startup"""
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
    """Create initial medication logs for all active medications"""
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
