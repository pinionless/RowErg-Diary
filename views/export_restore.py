import os
import json
import decimal
import datetime
from flask import Blueprint, current_app, flash, redirect, url_for, request, jsonify
from models import db, EquipmentType, Workout, MetricDescriptor, WorkoutSample, HeartRateSample, WorkoutHRZone, UserSetting

export_bp = Blueprint('export_restore', __name__, url_prefix='/export')

EXPORT_FILENAME = "export.json"
BACKUP_SUBDIR = "json_backup"

def get_export_filepath():
    # Defines the path for export.json, placing it in a 'json_backup' subdirectory
    # within the application root directory.
    # Both export and restore operations use this path.
    backup_dir = os.path.join(current_app.root_path, BACKUP_SUBDIR)
    return os.path.join(backup_dir, EXPORT_FILENAME)

def model_to_dict_converter(instance):
    """Converts a SQLAlchemy model instance to a dictionary, handling specific types."""
    data = {}
    for column in instance.__table__.columns:
        value = getattr(instance, column.name)
        if isinstance(value, (datetime.date, datetime.datetime)):
            data[column.name] = value.isoformat()
        elif isinstance(value, decimal.Decimal):
            data[column.name] = str(value)  # Store Decimal as string to preserve precision
        else:
            data[column.name] = value
    return data

@export_bp.route('/create', methods=['GET'])
def create_export():
    filepath = get_export_filepath() # Uses the path from get_export_filepath
    backup_dir = os.path.dirname(filepath)

    all_data = {}

    try:
        # Ensure the backup directory exists
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            current_app.logger.info(f"Created backup directory: {backup_dir}")

        all_data['user_settings'] = [model_to_dict_converter(item) for item in UserSetting.query.all()]
        all_data['equipment_types'] = [model_to_dict_converter(item) for item in EquipmentType.query.all()]
        all_data['metric_descriptors'] = [model_to_dict_converter(item) for item in MetricDescriptor.query.all()]
        all_data['workouts'] = [model_to_dict_converter(item) for item in Workout.query.all()]
        all_data['heart_rate_samples'] = [model_to_dict_converter(item) for item in HeartRateSample.query.all()]
        all_data['workout_samples'] = [model_to_dict_converter(item) for item in WorkoutSample.query.all()]
        all_data['workout_hr_zones'] = [model_to_dict_converter(item) for item in WorkoutHRZone.query.all()]

        with open(filepath, 'w') as f:
            json.dump(all_data, f, indent=4)
        
        flash(f'Successfully exported all data to {filepath}', 'success')
        current_app.logger.info(f"Data exported to {filepath}")
    except Exception as e:
        current_app.logger.error(f"Error creating export: {e}", exc_info=True)
        flash(f'Error creating export: {str(e)}', 'danger')
    
    return redirect(url_for('home')) # Assumes 'home' route exists

@export_bp.route('/restore', methods=['GET', 'POST'])
def restore_export():
    if request.method == 'GET':
        flash("To restore data from backup, please use a POST request. "
              "Warning: This will delete all current data before restoring.", "warning")
        # Ideally, show a confirmation page here or redirect to a page with a POST button.
        # For now, redirecting to home.
        return redirect(url_for('home'))

    # The restore operation reads from the same path defined by get_export_filepath(),
    # which is in the 'json_backup' subdirectory of the application's root directory.
    filepath = get_export_filepath()
    if not os.path.exists(filepath):
        flash(f'Export file {filepath} not found.', 'danger')
        return redirect(url_for('home'))

    try:
        with open(filepath, 'r') as f:
            data_to_restore = json.load(f)

        # 1. Delete existing data
        # Relies on ondelete='CASCADE' for Workout children (HeartRateSample, WorkoutSample, WorkoutHRZone)
        # If ondelete='CASCADE' is not set at DB level for FKs from WorkoutSample to MetricDescriptor,
        # or Workout to EquipmentType, this order is important.
        
        # Delete objects that depend on Workout first, or ensure Workout deletion cascades.
        # Given models.py, Workout deletion will cascade to HeartRateSample, WorkoutSample, WorkoutHRZone
        # due to `ondelete='CASCADE'` on their ForeignKey definitions.
        Workout.query.delete() # This should cascade to WorkoutSample, HeartRateSample, WorkoutHRZone
        db.session.commit() 

        # Now delete other tables. Order matters if there are remaining dependencies not handled by cascade.
        UserSetting.query.delete()
        MetricDescriptor.query.delete() # Safe after WorkoutSample (child of Workout) is deleted
        EquipmentType.query.delete()    # Safe after Workout is deleted
        db.session.commit()

        # 2. Insert new data in order of dependency
        for item_data in data_to_restore.get('user_settings', []):
            db.session.add(UserSetting(**item_data))
        db.session.commit()

        for item_data in data_to_restore.get('equipment_types', []):
            db.session.add(EquipmentType(**item_data))
        db.session.commit()

        for item_data in data_to_restore.get('metric_descriptors', []):
            db.session.add(MetricDescriptor(**item_data))
        db.session.commit()

        for item_data in data_to_restore.get('workouts', []):
            item_data['workout_date'] = datetime.date.fromisoformat(item_data['workout_date'])
            for field in ['duration_seconds', 'total_distance_meters', 'average_split_seconds_500m', 'total_isoreps']:
                if item_data.get(field) is not None:
                    item_data[field] = decimal.Decimal(item_data[field])
            # 'level' is float, no conversion needed if already float or string convertible to float
            if item_data.get('level') is not None:
                 item_data['level'] = float(item_data['level'])
            db.session.add(Workout(**item_data))
        db.session.commit()

        for item_data in data_to_restore.get('heart_rate_samples', []):
            db.session.add(HeartRateSample(**item_data))
        db.session.commit()

        for item_data in data_to_restore.get('workout_samples', []):
            if item_data.get('value') is not None:
                item_data['value'] = decimal.Decimal(item_data['value'])
            db.session.add(WorkoutSample(**item_data))
        db.session.commit()

        for item_data in data_to_restore.get('workout_hr_zones', []):
            for field in ['lower_bound_bpm', 'upper_bound_bpm', 'seconds_in_zone']:
                if item_data.get(field) is not None:
                    item_data[field] = decimal.Decimal(item_data[field])
            db.session.add(WorkoutHRZone(**item_data))
        db.session.commit()

        flash('Successfully restored data from backup.', 'success')
        current_app.logger.info(f"Data restored from {filepath}")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error restoring from export: {e}", exc_info=True)
        flash(f'Error restoring from export: {str(e)}', 'danger')
    
    return redirect(url_for('home'))

def register_routes(app):
    app.register_blueprint(export_bp)
