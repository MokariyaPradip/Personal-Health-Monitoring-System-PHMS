from flask import render_template, redirect, jsonify, request
from flask_login import login_required, current_user
from models.medicine_model import Medicine
from config import db
from models import Medication, MedicationLog
from datetime import date, datetime, timedelta
from utils.medication_schedule import get_scheduled_time_for_frequency
import logging

logger = logging.getLogger(__name__)


@login_required
def medication_page():
    """Display medication management page with search and view-all functionality.
    
    Renders the medication page showing user's current medications and available
    medicines from the master database. Supports search filtering by medicine name
    and pagination with optional view-all mode.
    
    Endpoints:
        GET /medication: Display medication management page
    
    Query Parameters:
        query (str, optional): Search term to filter medicines by name (case-insensitive)
        view_all (str, optional): Flag to display all medicines instead of default 9
    
    Display Logic:
        - Always shows ALL user's current medications (filtered by user_id)
        - If search query provided: Shows matching medicines (unlimited)
        - If view_all flag set: Shows all medicines in database
        - Default (no query, no flag): Shows first 9 medicines only
    
    Returns:
        Rendered medication.html template with:
            - meds: List[Medication] - User's current medications
            - medicines: List[Medicine] - Available medicines from master database
            - search_query: str - Current search term (or None)
            - view_all: str - View-all flag status (or None)
    
    Security:
        - Requires @login_required (authenticated session)
        - Medications filtered by current_user.user_id
        - Uses parameterized queries (SQLAlchemy ORM) to prevent SQL injection
    """

    meds = Medication.query.filter_by(user_id=current_user.user_id).all()
    
    # Check if there's a search query
    search_query = request.args.get('query')
    
    # view all
    view_all = request.args.get('view_all')  # <-- NEW FLAG

    if search_query:
        # If search query exists, filter medicines by name
        medicines = Medicine.query.filter(
            Medicine.medicine_name.ilike(f"%{search_query}%")
        ).all()
    else:
        if view_all:
            # View all medicines
            medicines = Medicine.query.all()
        else:
            # Default: show only 9
            medicines = Medicine.query.limit(9).all()

    # ===== Medication overview stats =====
    today = date.today()
    week_ago = today - timedelta(days=7)

    active_medications_count = sum(1 for med in meds if med.is_active())
    critical_medications_count = sum(1 for med in meds if med.is_critical)
    inactive_medications_count = len(meds) - active_medications_count
    ending_soon_count = sum(
        1
        for med in meds
        if med.is_active() and med.end_date and 0 <= (med.end_date - today).days <= 7
    )

    # ===== Last 7-day adherence snapshot =====
    last_7_day_logs = MedicationLog.query.filter(
        MedicationLog.user_id == current_user.user_id,
        MedicationLog.log_date >= week_ago
    ).all()

    taken_count = sum(1 for log in last_7_day_logs if log.status == 'taken')
    missed_count = sum(1 for log in last_7_day_logs if log.status == 'missed')
    pending_count = sum(1 for log in last_7_day_logs if log.status == 'pending')
    skipped_count = sum(1 for log in last_7_day_logs if log.status == 'skipped')
    total_logs = len(last_7_day_logs)
    adherence_rate = round((taken_count / total_logs) * 100, 2) if total_logs else 0

    today_pending_count = MedicationLog.query.filter_by(
        user_id=current_user.user_id,
        log_date=today,
        status='pending'
    ).count()

    medication_overview = {
        'total': len(meds),
        'active': active_medications_count,
        'inactive': inactive_medications_count,
        'critical': critical_medications_count,
        'ending_soon': ending_soon_count,
        'today_pending': today_pending_count
    }

    adherence_overview = {
        'rate': adherence_rate,
        'period': 'Last 7 days',
        'total': total_logs,
        'taken': taken_count,
        'missed': missed_count,
        'pending': pending_count,
        'skipped': skipped_count
    }
    
    return render_template(
        'medication.html',
        meds=meds,
        medicines=medicines,
        search_query=search_query,
        view_all=view_all,
        medication_overview=medication_overview,
        adherence_overview=adherence_overview
    )
    

@login_required
def add_medication():
    """Add new medication to user's regimen and auto-create today's logs if applicable.
    
    Creates a new Medication record with validation for dates, frequency, and dosage.
    If start_date is today, automatically generates MedicationLog entries for all
    scheduled times that haven't passed yet (e.g., if it's 10 AM and medication is
    3x daily at 9 AM, 2 PM, 9 PM, only 2 PM and 9 PM logs are created).
    
    Endpoints:
        POST /medication/add: Create new medication schedule
    
    Request Body (JSON):
        medicine_name (str): Medicine name (must exist in Medicine table)
        dosage (str): Dosage instruction (e.g., "10mg", "2 tablets")
        frequency (int): Daily frequency (1=once, 2=twice, 3=thrice, 4=four times, 6=six times)
        start_date (str): ISO format date (YYYY-MM-DD), cannot be in past
        end_date (str): ISO format date (YYYY-MM-DD), must be >= start_date
        is_critical (bool, optional): Critical medication flag (default: False)
    
    Validation Rules:
        - All fields required except is_critical
        - Frequency must be valid integer (1, 2, 3, 4, or 6)
        - start_date cannot be in the past
        - end_date must be >= start_date
        - Medicine must exist in Medicine table (case-insensitive search)
    
    Grace Period Logic for Same-Day Logs:
        - Uses get_scheduled_time_for_frequency() to determine time slots
        - Only creates logs for future scheduled times (filters by current time)
        - Sets status='pending' for all new logs
        - Logs are created with grace period consideration (defined per frequency)
    
    Returns:
        JSON response with creation status
            - 200: Medication added successfully
                  (includes logs_created count if start_date is today)
            - 400: Validation error (missing fields, invalid frequency, date validation)
            - 404: Medicine not found in master database
            - 500: Database error
    
    Side Effects:
        - Creates Medication record in database
        - If start_date == today: Creates MedicationLog records for future doses
        - Logs creation details to application logger
        - Flushes session before log creation to obtain medication_id
    
    Security:
        - Requires @login_required (authenticated session)
        - Associates medication with current_user.user_id
        - Validates medicine exists before creating medication
    
    Raises:
        Exception: Database commit failure or log creation error (rolled back)
    """
    data = request.get_json(silent=True) or {}
    
    # Validation
    medicine_name = data.get('medicine_name')
    dosage = data.get('dosage')
    frequency = data.get('frequency')
    is_critical = data.get('is_critical', False)
    
    if not medicine_name or not dosage or not frequency or not data.get('start_date') or not data.get('end_date'):
        return jsonify({"message": "All fields are required", "success": False}), 400

    # Convert frequency to integer
    try:
        frequency = int(frequency)
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Frequency must be a valid number (1=once, 2=twice, 3=thrice, 4=four times, 6=six times daily)"
        }), 400

    start_date = datetime.strptime(data['start_date'], "%Y-%m-%d").date()
    end_date = datetime.strptime(data['end_date'], "%Y-%m-%d").date()
    
    today = date.today()

    if start_date < today:
        return jsonify({
            "success": False,
            "message": "Start date cannot be in the past"
        }), 400

    if end_date < start_date:
        return jsonify({
            "success": False,
            "message": "End date must be after start date"
        }), 400

    
    try:
        # Check if medicine exists by name
        from models import Medicine
        medicine = Medicine.query.filter(
            Medicine.medicine_name.ilike(f"%{medicine_name}%")
        ).first()
        
        if not medicine:
            return jsonify({"message": "Medicine not found", "success": False}), 404
        
        medication = Medication(
            medicine_id=medicine.medicine_id,
            user_id=current_user.user_id,
            dosage=dosage,
            frequency=frequency,
            start_date=start_date,
            end_date=end_date,
            is_critical=is_critical
        )

        db.session.add(medication)
        db.session.flush()  # Flush to get medication_id without committing
        
        # ✅ IMPROVED: If start date is today, create medication logs for upcoming times only
        logs_created = 0
        if start_date == today:
            try:
                logger.info(f"Creating logs for medication {medication.medication_id}, frequency={frequency}")
                
                # Get scheduled times based on frequency
                scheduled_times = get_scheduled_time_for_frequency(frequency)
                
                logger.info(f"get_scheduled_time_for_frequency({frequency}) returned: {scheduled_times}")
                
                if scheduled_times and len(scheduled_times) > 0:
                    # Get current time to filter out past scheduled times
                    current_time = datetime.now().time()
                    
                    for scheduled_time in scheduled_times:
                        # Only create log if scheduled time is in the future
                        if scheduled_time > current_time:
                            try:
                                medication_log = MedicationLog(
                                    user_id=current_user.user_id,
                                    medication_id=medication.medication_id,
                                    log_date=today,
                                    scheduled_time=scheduled_time,
                                    status='pending'
                                )
                                db.session.add(medication_log)
                                logs_created += 1
                                logger.info(f"Created log for {medication.medication_id} at {scheduled_time}")
                            except Exception as time_error:
                                logger.error(f"Error creating individual log: {str(time_error)}", exc_info=True)
                                continue
                        else:
                            logger.info(f"Skipping past scheduled time {scheduled_time} for medication {medication.medication_id}")
                    
                    logger.info(f"Successfully created {logs_created} medication logs for medication {medication.medication_id}")
                else:
                    logger.warning(f"No scheduled times found for frequency: {frequency}")
                
            except Exception as log_error:
                logger.error(f"Error in medication log creation: {str(log_error)}", exc_info=True)
                # Continue even if log creation fails - medication is still added
        
        db.session.commit()
        
        msg = "Medication added successfully"
        if start_date == today and logs_created > 0:
            msg += f" and {logs_created} dose(s) scheduled for today"
        
        return jsonify({
            "success": True,
            "message": msg,
            "logs_created": logs_created
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding medication: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "message": f"Error adding medication: {str(e)}"
            }), 500
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding medication: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Error adding medication: {str(e)}"
            }), 500


@login_required
def delete_medication(id):
    """Delete medication with ownership verification and cascading log cleanup.
    
    Removes a medication from the user's regimen. Includes critical security check
    to ensure users can only delete their own medications. Associated MedicationLog
    entries are automatically deleted via SQLAlchemy cascade rules.
    
    Endpoints:
        DELETE /medication/<id>: Delete medication by ID
    
    Parameters:
        id (int): Medication ID to delete (from URL path)
    
    Validation:
        - Medication must exist (404 if not found)
        - Medication must belong to current_user (403 if unauthorized)
    
    Returns:
        JSON response with deletion status
            - 200: Medication deleted successfully
            - 403: Unauthorized (attempting to delete another user's medication)
            - 404: Medication not found
            - 500: Database error during deletion
    
    Side Effects:
        - Deletes Medication record from database
        - Cascades deletion to associated MedicationLog entries
        - Transaction is rolled back on error
    
    Security:
        - Requires @login_required (authenticated session)
        - CRITICAL ownership verification prevents unauthorized deletion
        - Uses parameterized query (SQLAlchemy ORM) to prevent injection
    
    Raises:
        Exception: Database deletion failure (rolled back automatically)
    """
    try:
        medication = Medication.query.get(id)
        
        if not medication:
            return jsonify({"message": "Could not delete medication", "success": False}), 404
        
        # ✅ CRITICAL: Verify ownership - user can only delete their own medications
        if medication.user_id != current_user.user_id:
            return jsonify({"message": "Unauthorized", "success": False}), 403
        
        db.session.delete(medication)
        db.session.commit()

        return jsonify({"message": "Medication deleted successfully", "success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error deleting medication", "success": False}), 500

# to add data in medicine table
@login_required
def add_medicine_master():
    """Add new medicine to the master Medicine database with duplicate checking.
    
    Administrative function to populate the Medicine master table with new medicines.
    Includes case-insensitive duplicate detection to prevent redundant entries.
    Intended for admin use or initial database seeding.
    
    Endpoints:
        POST /medicine/add-master: Add medicine to master database
    
    Request Body (JSON):
        medicine_name (str, required): Name of the medicine
        medicine_type (str, optional): Type/category (e.g., "Tablet", "Syrup", "Injection")
        purpose (str, required): Medical purpose or condition treated
        remark (str, optional): Additional notes or warnings
    
    Validation Rules:
        - medicine_name is required and stripped of whitespace
        - purpose is required and stripped of whitespace
        - medicine_type and remark are optional
        - Duplicate check is case-insensitive (uses ILIKE)
    
    Returns:
        JSON response with creation status
            - 200: Medicine added successfully
            - 400: Missing required fields (medicine_name or purpose)
            - 409: Medicine already exists (case-insensitive match)
    
    Side Effects:
        - Creates Medicine record in master database
        - Strips whitespace from all string fields
        - Database commit is immediate
    
    Security:
        - Requires @login_required (authenticated session)
        - Should ideally include admin role check (commented in code)
    
    Note:
        This function is intended for administrative purposes. Consider adding
        role-based access control (admin check) before production deployment.
    """
    data = request.get_json(silent=True) or {}
    medicine_name = data.get('medicine_name')
    medicine_type = data.get('medicine_type')
    purpose = data.get('purpose')
    remark = data.get('remark')
    

    if not medicine_name or not purpose:
        return jsonify({"success": False, "message": "Required fields missing"}), 400

    # DUPLICATE CHECK (case-insensitive)
    existing_medicine = Medicine.query.filter(
        Medicine.medicine_name.ilike(medicine_name)
    ).first()

    if existing_medicine:
        return jsonify({
            "success": False,
            "message": "Medicine already exists"
        }), 409

    # Add new medicine
    medicine = Medicine(
        medicine_name=medicine_name.strip(),
        medicine_type=medicine_type.strip() if medicine_type else None,
        purpose=purpose.strip() if purpose else None,
        remark=remark.strip() if remark else None
    )

    db.session.add(medicine)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Medicine added successfully"
    })

