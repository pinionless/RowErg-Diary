# views/submit_json_workout.py
import json
from flask import request, redirect, url_for, flash, current_app
from datetime import datetime
from sqlalchemy.exc import IntegrityError # Keep for other integrity errors
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

        equipment_name = "SKILLROW"
        equipment_type = EquipmentType.query.filter_by(name=equipment_name).first()
        if not equipment_type:
            equipment_type = EquipmentType(name=equipment_name)
            db.session.add(equipment_type)
            db.session.flush()

        cardio_log_id = workout_main_container.get('cardioLogId')
        if not cardio_log_id:
            flash('Cardio Log ID is missing.', 'danger')
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

        new_workout = Workout(
            cardio_log_id=cardio_log_id,
            equipment_type_id=equipment_type.equipment_type_id if equipment_type else None,
            workout_name=workout_main_container.get('name'),
            workout_date=workout_date_obj,
            target_description=workout_main_container.get('target')
            # total_isoreps will be populated after processing samples
        )
        db.session.add(new_workout)
        db.session.flush() # Get new_workout.workout_id

        # --- New MetricDescriptor handling ---
        descriptors_json = workout_main_container.get('analitics', {}).get('descriptor', [])
        # metric_descriptor_map will map the JSON's 'i' (original json_index) 
        # to the global MetricDescriptor object for this workout processing.
        metric_descriptor_map_for_samples = {} 
        
        isoreps_descriptor_id = None # <--- Added variable to store IsoReps descriptor ID

        for desc_data_from_json in descriptors_json:
            json_i = desc_data_from_json.get('i')
            metric_name_from_json = desc_data_from_json.get('pr', {}).get('name')
            unit_of_measure_from_json = desc_data_from_json.get('pr', {}).get('um')

            if metric_name_from_json is None: # Skip if no metric name
                current_app.logger.warning(f"Skipping descriptor due to missing name: {desc_data_from_json}")
                continue

            # Find or create the global MetricDescriptor
            metric_descriptor_entry = MetricDescriptor.query.filter_by(
                metric_name=metric_name_from_json,
                unit_of_measure=unit_of_measure_from_json
            ).first()

            if not metric_descriptor_entry:
                try:
                    metric_descriptor_entry = MetricDescriptor(
                        metric_name=metric_name_from_json,
                        unit_of_measure=unit_of_measure_from_json
                    )
                    db.session.add(metric_descriptor_entry)
                    db.session.flush() # Flush to get its ID and ensure it's in DB for next lookup
                except IntegrityError: # Handles rare race condition if using multiple workers, or retries
                    db.session.rollback()
                    metric_descriptor_entry = MetricDescriptor.query.filter_by(
                        metric_name=metric_name_from_json,
                        unit_of_measure=unit_of_measure_from_json
                    ).first()
                    if not metric_descriptor_entry: # Should not happen if unique constraint is working
                        raise Exception(f"Failed to create or find metric descriptor: {metric_name_from_json} ({unit_of_measure_from_json})")


            if json_i is not None and metric_descriptor_entry:
                metric_descriptor_map_for_samples[json_i] = metric_descriptor_entry
                # <--- Check if this is the IsoReps descriptor
                if metric_name_from_json == 'IsoReps' and unit_of_measure_from_json == 'Number':
                    isoreps_descriptor_id = metric_descriptor_entry.metric_descriptor_id
        
        # --- Process WorkoutSamples using the new map ---
        samples_json = workout_main_container.get('analitics', {}).get('samples', [])
        
        # Keep track of the last IsoReps value
        last_isoreps_value = None # <--- Added variable for IsoReps total
        
        for sample_json in samples_json:
            time_offset = sample_json.get('t')
            values_from_json = sample_json.get('vs', []) 
            for original_json_index, value in enumerate(values_from_json):
                descriptor_obj = metric_descriptor_map_for_samples.get(original_json_index)
                if descriptor_obj:
                    workout_sample = WorkoutSample(
                        workout_id=new_workout.workout_id,
                        metric_descriptor_id=descriptor_obj.metric_descriptor_id,
                        time_offset_seconds=time_offset,
                        value=value
                    )
                    db.session.add(workout_sample)
                    
                    # <--- Capture IsoReps value if it's the correct descriptor
                    if descriptor_obj.metric_descriptor_id == isoreps_descriptor_id:
                        last_isoreps_value = value

        # --- Process summary data for Workout object (duration, distance, split, and IsoReps) ---
        extracted_duration_seconds = None
        calculated_total_distance_meters = None
        calculated_average_split_seconds_500m = None
        
        summary_entries_json = workout_main_container.get('data', [])
        for entry_json in summary_entries_json:
            property_key = entry_json.get('property')
            if property_key == 'Move': continue
            if property_key == 'Duration':
                try:
                    raw_duration_value = float(entry_json.get('rawValue'))
                    unit = entry_json.get('uM', '').lower()
                    if unit in ["min", "minute", "minutes"]: extracted_duration_seconds = raw_duration_value * 60
                    elif unit in ["h", "hour", "hours"]: extracted_duration_seconds = raw_duration_value * 3600
                    elif unit in ["ms", "millisecond", "milliseconds"]: extracted_duration_seconds = raw_duration_value / 1000.0
                    elif unit in ["s", "sec", "second", "seconds"] or not unit: extracted_duration_seconds = raw_duration_value
                    if extracted_duration_seconds is not None: break
                except: pass
        
        # Try to get total distance from metric samples using the mapped global descriptors
        distance_metric_descriptor_id_to_check = None
        for _json_idx, desc_obj_in_map in metric_descriptor_map_for_samples.items():
            if desc_obj_in_map.metric_name and 'distance' in desc_obj_in_map.metric_name.lower():
                distance_metric_descriptor_id_to_check = desc_obj_in_map.metric_descriptor_id
                break
        
        if distance_metric_descriptor_id_to_check:
            last_distance_sample = WorkoutSample.query.filter_by(
                workout_id=new_workout.workout_id,
                metric_descriptor_id=distance_metric_descriptor_id_to_check
            ).order_by(WorkoutSample.time_offset_seconds.desc()).first()
            if last_distance_sample and last_distance_sample.value is not None:
                calculated_total_distance_meters = float(last_distance_sample.value)
        
        if calculated_total_distance_meters is None: # Fallback to summary_entries_json if not in samples
            for entry_json in summary_entries_json:
                pkey = entry_json.get('property', '').lower()
                if 'distance' in pkey:
                    try:
                        val = float(entry_json.get('rawValue'))
                        unit = entry_json.get('uM', '').lower()
                        if unit == 'km': calculated_total_distance_meters = val * 1000
                        elif unit == 'mi': calculated_total_distance_meters = val * 1609.34
                        elif unit == 'm' or not unit: calculated_total_distance_meters = val
                        if calculated_total_distance_meters is not None: break
                    except: pass
        
        if extracted_duration_seconds is not None and calculated_total_distance_meters is not None and calculated_total_distance_meters > 0:
            calculated_average_split_seconds_500m = (extracted_duration_seconds / calculated_total_distance_meters) * 500
        
        new_workout.duration_seconds = extracted_duration_seconds
        new_workout.total_distance_meters = calculated_total_distance_meters
        new_workout.average_split_seconds_500m = calculated_average_split_seconds_500m
        new_workout.total_isoreps = last_isoreps_value # <--- Assign IsoReps value to the workout

        # HeartRateSamples and WorkoutHRZones processing (remains the same)
        hr_samples_json = json_data.get('hr', workout_main_container.get('hr', workout_main_container.get('analitics', {}).get('hr', [])))
        if hr_samples_json:
            for hr_item in hr_samples_json:
                if hr_item.get('hr') is not None:
                    db.session.add(HeartRateSample(workout_id=new_workout.workout_id, time_offset_seconds=hr_item.get('t'), heart_rate_bpm=hr_item.get('hr')))
        
        hr_zones_json = json_data.get('hrZones', workout_main_container.get('hrZones', workout_main_container.get('analitics', {}).get('hrZones', [])))
        if hr_zones_json:
            for zone_item in hr_zones_json:
                db.session.add(WorkoutHRZone(workout_id=new_workout.workout_id, zone_name=zone_item.get('name'), color_hex=zone_item.get('color'), lower_bound_bpm=zone_item.get('lowerBound'), upper_bound_bpm=zone_item.get('upperBound'), seconds_in_zone=zone_item.get('secondsInZone')))

        db.session.commit()
        flash('Workout data submitted successfully!', 'success')
        return redirect(url_for('home'))

    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(f"IntegrityError during workout submission: {e.orig}", exc_info=True)
        flash(f'Database integrity error: {str(e.orig)}. Could not submit workout.', 'danger')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error submitting workout: {e}', exc_info=True)
        flash(f'Error submitting workout: {str(e)}', 'danger')
    
    return redirect(url_for('home'))

# register_routes remains the same
def register_routes(app):
    app.add_url_rule('/submit_json_workout', endpoint='submit_json_workout', view_func=submit_json_workout, methods=['POST'])