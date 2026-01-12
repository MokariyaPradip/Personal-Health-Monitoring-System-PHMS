from flask import render_template, session, redirect, jsonify, request
from config import db
from models import Medication


def medication_page():
    """Display medication page"""
    if 'user_id' not in session:
        return redirect('/login')

    meds = Medication.query.filter_by(user_id=session['user_id']).all()
    return render_template('medication.html', meds=meds)


def add_medication():
    """Add new medication"""
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized", "success": False}), 401

    data = request.json
    
    # Validation
    medicine_id = data.get('medicine_id')
    dosage = data.get('dosage')
    frequency = data.get('frequency')
    
    if not medicine_id or not dosage or not frequency:
        return jsonify({"message": "All fields are required", "success": False}), 400
    
    try:
        # Check if medicine exists
        from models import Medicine
        medicine = Medicine.query.get(medicine_id)
        if not medicine:
            return jsonify({"message": "Medicine not found", "success": False}), 404
        
        medication = Medication(
            medicine_id=medicine_id,
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


def update_medication(id):
    """Update medication details"""
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized", "success": False}), 401

    try:
        data = request.json
        medication = Medication.query.get(id)
        
        if not medication:
            return jsonify({"message": "Medication not found", "success": False}), 404
        
        # Verify ownership
        if medication.user_id != session['user_id']:
            return jsonify({"message": "Unauthorized access", "success": False}), 403
        
        dosage = data.get('dosage')
        frequency = data.get('frequency')
        
        if not dosage or not frequency:
            return jsonify({"message": "All fields are required", "success": False}), 400

        medication.dosage = dosage
        medication.frequency = frequency

        db.session.commit()
        return jsonify({"message": "Medication updated successfully", "success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error updating medication: {str(e)}", "success": False}), 500


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
