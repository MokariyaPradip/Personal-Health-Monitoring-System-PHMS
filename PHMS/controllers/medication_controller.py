from flask import render_template, redirect, jsonify, request
from flask_login import login_required, current_user
from models.medicine_model import Medicine
from config import db
from models import Medication, MedicationLog
from datetime import date, datetime
from utils.medication_schedule import get_intake_times
import logging

logger = logging.getLogger(__name__)


@login_required
def medication_page():
    """Display medication page with optional search functionality"""

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
    
    return render_template(
        'medication.html',
        meds=meds,
        medicines=medicines,
        search_query=search_query,
        view_all=view_all
    )
    

@login_required
def add_medication():
    """Add new medication and create logs if start date is today"""
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
        
        # ✅ IMPROVED: If start date is today, create medication logs for today
        logs_created = 0
        if start_date == today:
            try:
                logger.info(f"Creating logs for medication {medication.medication_id}, frequency={frequency}")
                
                # Get scheduled times based on frequency
                scheduled_times = get_intake_times(frequency)
                
                logger.info(f"get_intake_times({frequency}) returned: {scheduled_times}")
                
                if scheduled_times and len(scheduled_times) > 0:
                    for scheduled_time in scheduled_times:
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
    """Delete medication with ownership verification"""
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

