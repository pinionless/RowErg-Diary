# ========================================================
# = submit_manual_workout.py - View for manual workout submission
# ========================================================
import uuid
from flask import request, redirect, url_for, flash, current_app
from datetime import datetime
from models import db, EquipmentType, Workout
from utils import parse_duration_to_seconds

# --------------------------------------------------------
# - Manual Workout Submission View Function
#---------------------------------------------------------
def submit_manual_workout():
    if request.method == 'POST':
        # == Form Data Retrieval ============================================
        workout_name_form = request.form.get('workoutName')
        date_str = request.form.get('workoutDate')
        time_str = request.form.get('workoutTime')
        distance_str = request.form.get('workoutDistance')
        level_str = request.form.get('workoutLevel')
        notes = request.form.get('workoutNotes')
        equipment_type_id_form = request.form.get('equipmentType')

        # == Validation ============================================
        # -- Mandatory Fields -------------------
        if not date_str or not time_str or not distance_str or not equipment_type_id_form:
            flash('Date, Time, Distance, and Equipment are required fields.', 'danger')
            return redirect(url_for('home'))

        workout_name = workout_name_form if workout_name_form else "Rowing" # Default workout name

        # -- Date Validation -------------------
        try:
            workout_date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash(f'Invalid date format: {date_str}. Expected YYYY-MM-DD.', 'danger')
            return redirect(url_for('home'))

        # -- Duration Validation -------------------
        duration_seconds_val = parse_duration_to_seconds(time_str)
        if duration_seconds_val is None or duration_seconds_val <=0:
            flash(f'Invalid time format: {time_str}. Use HH:MM:SS.ms, MM:SS.ms, or S.ms.', 'danger')
            return redirect(url_for('home'))

        # -- Distance Validation -------------------
        try:
            total_distance_meters_val = float(distance_str)
            if total_distance_meters_val <= 0:
                flash('Distance must be a positive number.', 'danger')
                return redirect(url_for('home'))
        except ValueError:
            flash('Invalid distance format. Must be a number.', 'danger')
            return redirect(url_for('home'))

        # -- Level Validation -------------------
        level_val = None
        if level_str: # Level is optional
            try:
                level_val = float(level_str)
                if level_val < 0: # Assuming level should not be negative
                    flash('Level must be a non-negative number.', 'danger')
                    return redirect(url_for('home'))
            except ValueError:
                flash('Invalid level format. Must be a number (e.g., 5 or 5.5).', 'danger')
                return redirect(url_for('home'))

        # == Calculate Split ============================================
        average_split_val = None
        if total_distance_meters_val > 0 and duration_seconds_val > 0:
            average_split_val = (duration_seconds_val / total_distance_meters_val) * 500 # Calculate 500m split

        # == Equipment Validation ============================================
        try:
            equipment_type_id_val = int(equipment_type_id_form)
            equipment_type = EquipmentType.query.get(equipment_type_id_val)
            if not equipment_type:
                flash('Invalid equipment selected.', 'danger')
                return redirect(url_for('home'))
        except (ValueError, TypeError):
            flash('Invalid equipment ID format.', 'danger')
            return redirect(url_for('home'))

        # == Create Workout Object and Save to Database ============================================
        try:
            cardio_log_id = f"manual_{uuid.uuid4()}" # Generate a unique ID for manual entries

            new_workout = Workout(
                cardio_log_id=cardio_log_id,
                equipment_type_id=equipment_type_id_val,
                workout_name=workout_name,
                workout_date=workout_date_obj,
                target_description=None, # Manual entries might not have a target description
                duration_seconds=duration_seconds_val,
                total_distance_meters=total_distance_meters_val,
                average_split_seconds_500m=average_split_val,
                total_isoreps=None, # Not applicable for typical manual rowing entries
                notes=notes if notes else None,
                level=level_val
            )
            
            db.session.add(new_workout)
            db.session.commit()
            flash('Manual workout added successfully!', 'success')
            return redirect(url_for('details', workout_id=new_workout.workout_id)) # Redirect to the new workout's detail page

        except Exception as e: # Catch any database or other errors during workout creation
            db.session.rollback() # Rollback transaction on error
            current_app.logger.error(f"Error adding manual workout: {e}", exc_info=True)
            flash(f'Error adding manual workout: {str(e)}', 'danger')
            return redirect(url_for('home'))
    
    # == Handle GET Request ============================================
    # If accessed via GET, redirect to home (form is POST only)
    return redirect(url_for('home'))

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the manual workout submission route with the Flask application
def register_routes(app):
    app.add_url_rule('/submit_manual_workout', endpoint='submit_manual_workout', view_func=submit_manual_workout, methods=['POST'])