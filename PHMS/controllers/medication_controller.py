from flask import render_template, session, redirect, jsonify, request
from models.medicine_model import Medicine
from config import db
from models import Medication


def medication_page():
    """Display medication page with optional search functionality"""
    if 'user_id' not in session:
        return redirect('/login')

    meds = Medication.query.filter_by(user_id=session['user_id']).all()
    
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
    

def add_medication():
    """Add new medication"""
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized", "success": False}), 401

    data = request.json
    
    # Validation
    medicine_name = data.get('medicine_name')
    dosage = data.get('dosage')
    frequency = data.get('frequency')

    if not medicine_name or not dosage or not frequency:
        return jsonify({"message": "All fields are required", "success": False}), 400
    
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
            user_id=session['user_id'],
            dosage=dosage,
            frequency=frequency
        )

        db.session.add(medication)
        db.session.commit()
        return jsonify({"message": "Medication added successfully", "success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error adding medication: {str(e)}", "success": False}), 500


def delete_medication(id):
    """Delete medication"""
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized", "success": False}), 401

    try:
        medication = Medication.query.get(id)
        
        if not medication:
            return jsonify({"message": "Medication not found", "success": False}), 404
        
        # Verify ownership - user can only delete their own medications
        if medication.user_id != session['user_id']:
            return jsonify({"message": "Unauthorized access", "success": False}), 403
        
        db.session.delete(medication)
        db.session.commit()

        return jsonify({"message": "Medication deleted successfully", "success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error deleting medication: {str(e)}", "success": False}), 500

# to add data in medicine table
def add_medicine_master():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.json
    medicine_name = data.get('medicine_name')
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
        purpose=purpose.strip(),
        remark=remark.strip() if remark else None
    )

    db.session.add(medicine)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Medicine added successfully"
    })

