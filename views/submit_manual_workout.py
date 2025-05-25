# views/submit_manual_workout.py
import uuid
from flask import request, redirect, url_for, flash, current_app
from datetime import datetime
from models import db, EquipmentType, Workout
from utils import parse_duration_to_seconds # Assuming you might create/use such a utility

def submit_manual_workout():
    if request.method == 'POST':
        workout_name_form = request.form.get('workoutName')
        date_str = request.form.get('workoutDate')
        time_str = request.form.get('workoutTime')
        distance_str = request.form.get('workoutDistance')
        # level_str = request.form.get('workoutLevel') #later create new table for levels
        notes = request.form.get('workoutNotes')

        # --- Validation ---
        if not date_str or not time_str or not distance_str:
            flash('Date, Time, and Distance are required fields.', 'danger')
            return redirect(url_for('home'))

        workout_name = workout_name_form if workout_name_form else "Rowing"

        try:
            workout_date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash(f'Invalid date format: {date_str}. Expected YYYY-MM-DD.', 'danger')
            return redirect(url_for('home'))

        duration_seconds_val = parse_duration_to_seconds(time_str)
        if duration_seconds_val is None or duration_seconds_val <=0:
            flash(f'Invalid time format: {time_str}. Use HH:MM:SS.ms, MM:SS.ms, or S.ms.', 'danger')
            return redirect(url_for('home'))

        try:
            total_distance_meters_val = float(distance_str)
            if total_distance_meters_val <= 0:
                flash('Distance must be a positive number.', 'danger')
                return redirect(url_for('home'))
        except ValueError:
            flash('Invalid distance format. Must be a number.', 'danger')
            return redirect(url_for('home'))

        # --- Calculate Split ---
        average_split_val = None
        if total_distance_meters_val > 0 and duration_seconds_val > 0:
            average_split_val = (duration_seconds_val / total_distance_meters_val) * 500

        # --- Get or Create Equipment Type ---
        equipment_name = "Manual Entry" # Or "RowErgometer" if it's always a rower
        equipment_type = EquipmentType.query.filter_by(name=equipment_name).first()
        if not equipment_type:
            equipment_type = EquipmentType(name=equipment_name)
            db.session.add(equipment_type)
            db.session.flush() # To get ID if new

        # --- Create Workout Object ---
        try:
            # Generate a unique cardio_log_id for manual entries
            # Using a combination of a prefix and a UUID to ensure uniqueness
            cardio_log_id = f"manual_{uuid.uuid4()}"

            new_workout = Workout(
                cardio_log_id=cardio_log_id,
                equipment_type_id=equipment_type.equipment_type_id,
                workout_name=workout_name,
                workout_date=workout_date_obj,
                #target_description=level_str if level_str else None, # Using level as target description
                duration_seconds=duration_seconds_val,
                total_distance_meters=total_distance_meters_val,
                average_split_seconds_500m=average_split_val,
                total_isoreps=None,  # IsoReps are not provided in manual entry
                notes=notes if notes else None
            )
            
            db.session.add(new_workout)
            db.session.commit()
            flash('Manual workout added successfully!', 'success')
            return redirect(url_for('details', workout_id=new_workout.workout_id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding manual workout: {e}", exc_info=True)
            flash(f'Error adding manual workout: {str(e)}', 'danger')
            return redirect(url_for('home'))
    
    # Should not be reached via GET if form is POST only
    return redirect(url_for('home'))

def register_routes(app):
    app.add_url_rule('/submit_manual_workout', endpoint='submit_manual_workout', view_func=submit_manual_workout, methods=['POST'])