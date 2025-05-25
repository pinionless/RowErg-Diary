# views/submit_json_workout.py
import json
from flask import request, redirect, url_for, flash, current_app
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from models import db, EquipmentType, Workout, MetricDescriptor, WorkoutSample, HeartRateSample, WorkoutHRZone
from utils import format_duration_ms

def submit_json_workout():
    raw_json_data = request.form.get('jsonData')
    if not raw_json_data:
        flash('No JSON data provided.', 'danger')
        return redirect(url_for('home'))

    try:
        json_data = json.loads(raw_json_data)
    except json.JSONDecodeError:
        flash('Invalid JSON format.', 'danger')
        return redirect(url_for('home'))

    try:
        workout_main_container = json_data.get('data', {})
        if not workout_main_container:
            flash('Main "data" object is missing or empty in the submitted JSON.', 'danger')
            return redirect(url_for('home'))

        # --- Hardcode equipment_name to "SKILLROW" ---
        equipment_name = "SKILLROW"  # <--- HARDCODED VALUE
        equipment_type = None
        
        # Find or create the "SKILLROW" equipment type
        if equipment_name: # This will always be true now
            equipment_type = EquipmentType.query.filter_by(name=equipment_name).first()
            if not equipment_type:
                equipment_type = EquipmentType(name=equipment_name)
                db.session.add(equipment_type)
                db.session.flush() # Ensure equipment_type_id is available if needed immediately

        cardio_log_id = workout_main_container.get('cardioLogId')
        if not cardio_log_id:
            flash('Cardio Log ID is missing within the main "data" object of the JSON.', 'danger')
            return redirect(url_for('home'))

        existing_workout = Workout.query.filter_by(cardio_log_id=cardio_log_id).first()
        if existing_workout:
            flash(f'Workout with Cardio Log ID {cardio_log_id} already exists.', 'warning')
            return redirect(url_for('details', workout_id=existing_workout.workout_id))

        workout_date_str = workout_main_container.get('date')
        try:
            workout_date_obj = datetime.strptime(workout_date_str, '%d/%m/%Y').date()
        except (ValueError, TypeError):
            flash(f'Invalid date format: {workout_date_str}. Expected DD/MM/YYYY.', 'danger')
            return redirect(url_for('home'))

        extracted_duration_seconds = None
        calculated_total_distance_meters = None
        calculated_average_split_seconds_500m = None

        summary_entries_json = workout_main_container.get('data', [])
        for entry_json in summary_entries_json:
            property_key = entry_json.get('property')
            if property_key == 'Move':
                continue
            
            if property_key == 'Duration':
                try:
                    raw_duration_value = float(entry_json.get('rawValue'))
                    unit_of_measure = entry_json.get('uM', '').lower()
                    
                    if unit_of_measure in ["min", "minute", "minutes"]:
                        extracted_duration_seconds = raw_duration_value * 60
                    elif unit_of_measure in ["h", "hour", "hours"]:
                        extracted_duration_seconds = raw_duration_value * 3600
                    elif unit_of_measure in ["ms", "millisecond", "milliseconds"]:
                        extracted_duration_seconds = raw_duration_value / 1000.0
                    elif unit_of_measure in ["s", "sec", "second", "seconds"] or not unit_of_measure:
                        extracted_duration_seconds = raw_duration_value
                    
                    if extracted_duration_seconds is not None:
                        break 
                except (ValueError, TypeError, AttributeError):
                    current_app.logger.warning(f"Could not parse duration from summary entry: {entry_json}")
                    pass

        new_workout = Workout(
            cardio_log_id=cardio_log_id,
            equipment_type_id=equipment_type.equipment_type_id if equipment_type else None, # equipment_type will be SKILLROW if found/created
            workout_name=workout_main_container.get('name'),
            workout_date=workout_date_obj,
            target_description=workout_main_container.get('target')
        )
        db.session.add(new_workout)
        db.session.flush()

        descriptors_json = workout_main_container.get('analitics', {}).get('descriptor', [])
        metric_descriptor_map = {}
        for desc_json in descriptors_json:
            metric_desc = MetricDescriptor(
                workout_id=new_workout.workout_id,
                json_index=desc_json.get('i'),
                metric_name=desc_json.get('pr', {}).get('name'),
                unit_of_measure=desc_json.get('pr', {}).get('um')
            )
            db.session.add(metric_desc)
            db.session.flush()
            metric_descriptor_map[metric_desc.json_index] = metric_desc

        samples_json = workout_main_container.get('analitics', {}).get('samples', [])
        for sample_json in samples_json:
            time_offset = sample_json.get('t')
            values = sample_json.get('vs', [])
            for i, value in enumerate(values):
                descriptor = metric_descriptor_map.get(i)
                if descriptor:
                    workout_sample = WorkoutSample(
                        workout_id=new_workout.workout_id,
                        metric_descriptor_id=descriptor.metric_descriptor_id,
                        time_offset_seconds=time_offset,
                        value=value
                    )
                    db.session.add(workout_sample)

        hr_samples_json = json_data.get('hr')
        if not hr_samples_json:
            hr_samples_json = workout_main_container.get('hr')
            if not hr_samples_json:
                analitics_data = workout_main_container.get('analitics', {})
                hr_samples_json = analitics_data.get('hr', [])
        
        if hr_samples_json:
            for hr_sample_json_item in hr_samples_json:
                hr_val = hr_sample_json_item.get('hr')
                time_val = hr_sample_json_item.get('t')
                if hr_val is not None:
                    hr_sample = HeartRateSample(
                        workout_id=new_workout.workout_id,
                        time_offset_seconds=time_val,
                        heart_rate_bpm=hr_val
                    )
                    db.session.add(hr_sample)

        hr_zones_json = json_data.get('hrZones')
        if not hr_zones_json:
            hr_zones_json = workout_main_container.get('hrZones')
            if not hr_zones_json:
                analitics_data = workout_main_container.get('analitics', {})
                hr_zones_json = analitics_data.get('hrZones', [])
        
        if hr_zones_json:
            for zone_json_item in hr_zones_json:
                hr_zone = WorkoutHRZone(
                    workout_id=new_workout.workout_id,
                    zone_name=zone_json_item.get('name'),
                    color_hex=zone_json_item.get('color'),
                    lower_bound_bpm=zone_json_item.get('lowerBound'),
                    upper_bound_bpm=zone_json_item.get('upperBound'),
                    seconds_in_zone=zone_json_item.get('secondsInZone')
                )
                db.session.add(hr_zone)
        
        distance_descriptor = MetricDescriptor.query.filter(
            MetricDescriptor.workout_id == new_workout.workout_id,
            MetricDescriptor.metric_name.ilike('%distance%')
        ).first()
        
        if distance_descriptor:
            last_distance_sample = WorkoutSample.query.filter_by(
                workout_id=new_workout.workout_id,
                metric_descriptor_id=distance_descriptor.metric_descriptor_id
            ).order_by(WorkoutSample.time_offset_seconds.desc()).first()
            if last_distance_sample and last_distance_sample.value is not None:
                calculated_total_distance_meters = float(last_distance_sample.value)
        
        if calculated_total_distance_meters is None:
            for entry_json in summary_entries_json:
                property_key = entry_json.get('property', '').lower()
                if 'distance' in property_key: 
                    try:
                        raw_dist_value = float(entry_json.get('rawValue'))
                        unit_of_measure = entry_json.get('uM', '').lower()
                        if unit_of_measure == 'km':
                            calculated_total_distance_meters = raw_dist_value * 1000
                        elif unit_of_measure == 'mi':
                            calculated_total_distance_meters = raw_dist_value * 1609.34
                        elif unit_of_measure == 'm' or not unit_of_measure:
                            calculated_total_distance_meters = raw_dist_value
                        
                        if calculated_total_distance_meters is not None:
                            break 
                    except (ValueError, TypeError, AttributeError):
                        current_app.logger.warning(f"Could not parse distance from summary entry: {entry_json}")
                        pass
        
        if extracted_duration_seconds is not None and calculated_total_distance_meters is not None and calculated_total_distance_meters > 0:
            calculated_average_split_seconds_500m = (extracted_duration_seconds / calculated_total_distance_meters) * 500
        
        new_workout.duration_seconds = extracted_duration_seconds
        new_workout.total_distance_meters = calculated_total_distance_meters
        new_workout.average_split_seconds_500m = calculated_average_split_seconds_500m
        
        db.session.commit()
        flash('Workout data submitted successfully!', 'success')
        return redirect(url_for('details', workout_id=new_workout.workout_id))

    except IntegrityError as e:
        db.session.rollback()
        if 'cardio_log_id' in str(e.orig).lower() and 'unique constraint' in str(e.orig).lower():
             flash(f'Workout with Cardio Log ID {cardio_log_id} already exists. Integrity error.', 'danger')
        else:
            flash(f'Database integrity error: {str(e.orig)}. Please check data.', 'danger')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error submitting workout: {e}', exc_info=True)
        flash(f'Error submitting workout: {str(e)}', 'danger')
    
    return redirect(url_for('home'))

def register_routes(app):
    app.add_url_rule('/submit_json_workout', endpoint='submit_json_workout', view_func=submit_json_workout, methods=['POST'])