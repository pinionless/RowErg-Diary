# ========================================================
# = submit_json_workout.py - View for submitting workout data via JSON
# ========================================================
import json
from flask import request, redirect, url_for, flash, current_app
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from models import db, EquipmentType, Workout, MetricDescriptor, WorkoutSample, HeartRateSample, WorkoutHRZone
from utils import format_duration_ms # Retained as it might be used for debugging or future display logic, though not directly in current processing

# --------------------------------------------------------
# - JSON Workout Submission View Function
#---------------------------------------------------------
def submit_json_workout():
    # == Form Data Retrieval ============================================
    raw_json_data = request.form.get('jsonData') # Get raw JSON string from form
    workout_notes = request.form.get('jsonNotes') # Get workout notes from form

    # == Initial JSON Data Validation ============================================
    if not raw_json_data:
        flash('No JSON data provided.', 'danger')
        return redirect(url_for('home'))

    try:
        json_data = json.loads(raw_json_data) # Parse JSON string
    except json.JSONDecodeError:
        flash('Invalid JSON format.', 'danger')
        return redirect(url_for('home'))

    try:
        # == Main Workout Data Extraction ============================================
        workout_main_container = json_data.get('data', {}) # Main data object in JSON
        if not workout_main_container:
            flash('Main "data" object is missing or empty in the submitted JSON.', 'danger')
            return redirect(url_for('home'))

        # == Equipment Type Handling ============================================
        equipment_name = "SKILLROW" # Default equipment for JSON submissions
        equipment_type = EquipmentType.query.filter_by(name=equipment_name).first()
        if not equipment_type: # Create if not exists
            equipment_type = EquipmentType(name=equipment_name)
            db.session.add(equipment_type)
            db.session.flush() # Ensure ID is available

        # == Cardio Log ID and Existing Workout Check ============================================
        cardio_log_id = workout_main_container.get('cardioLogId')
        if not cardio_log_id:
            flash('Cardio Log ID is missing.', 'danger')
            return redirect(url_for('home'))

        existing_workout = Workout.query.filter_by(cardio_log_id=cardio_log_id).first()
        if existing_workout:
            flash(f'Workout with Cardio Log ID {cardio_log_id} already exists.', 'warning')
            # Future: Consider updating notes if new notes are provided for an existing workout
            return redirect(url_for('details', workout_id=existing_workout.workout_id))

        # == Workout Date Parsing ============================================
        workout_date_str = workout_main_container.get('date')
        try:
            workout_date_obj = datetime.strptime(workout_date_str, '%d/%m/%Y').date() # Expected format DD/MM/YYYY
        except (ValueError, TypeError):
            flash(f'Invalid date format: {workout_date_str}. Expected DD/MM/YYYY.', 'danger')
            return redirect(url_for('home'))

        # == Create Initial Workout Object ============================================
        new_workout = Workout(
            cardio_log_id=cardio_log_id,
            equipment_type_id=equipment_type.equipment_type_id if equipment_type else None,
            workout_name=workout_main_container.get('name'),
            workout_date=workout_date_obj,
            target_description=workout_main_container.get('target'),
            notes=workout_notes if workout_notes and workout_notes.strip() else None # Save notes if provided
            # Summary fields (duration, distance, split, isoreps) will be populated later
        )
        db.session.add(new_workout)
        db.session.flush() # Get new_workout.workout_id for foreign key relations

        # == Metric Descriptor Processing ============================================
        # -- Create or Get Metric Descriptors from JSON -------------------
        descriptors_json = workout_main_container.get('analitics', {}).get('descriptor', [])
        metric_descriptor_map_for_samples = {} # Maps JSON index 'i' to MetricDescriptor object
        
        isoreps_descriptor_id = None # To identify IsoReps metric for summary
        level_descriptor_json_index = None # To identify Level metric's index in JSON samples 'vs' array

        for desc_data_from_json in descriptors_json:
            json_i = desc_data_from_json.get('i') # Index from JSON used to map samples
            metric_name_from_json = desc_data_from_json.get('pr', {}).get('name')
            unit_of_measure_from_json = desc_data_from_json.get('pr', {}).get('um')

            if metric_name_from_json is None: # Skip if essential data is missing
                current_app.logger.warning(f"Skipping descriptor due to missing name: {desc_data_from_json}")
                continue

            # -- Find or Create MetricDescriptor in DB -------------------
            metric_descriptor_entry = MetricDescriptor.query.filter_by(
                metric_name=metric_name_from_json,
                unit_of_measure=unit_of_measure_from_json
            ).first()

            if not metric_descriptor_entry: # If descriptor doesn't exist, create it
                try:
                    metric_descriptor_entry = MetricDescriptor(
                        metric_name=metric_name_from_json,
                        unit_of_measure=unit_of_measure_from_json
                    )
                    db.session.add(metric_descriptor_entry)
                    db.session.flush() # Ensure ID is available
                except IntegrityError: # Handle rare race condition if another process creates it
                    db.session.rollback()
                    metric_descriptor_entry = MetricDescriptor.query.filter_by(
                        metric_name=metric_name_from_json,
                        unit_of_measure=unit_of_measure_from_json
                    ).first()
                    if not metric_descriptor_entry: # If still not found, raise error
                        raise Exception(f"Failed to create or find metric descriptor: {metric_name_from_json} ({unit_of_measure_from_json})")

            # -- Populate Map and Identify IsoReps -------------------
            if json_i is not None and metric_descriptor_entry:
                metric_descriptor_map_for_samples[json_i] = metric_descriptor_entry
                if metric_name_from_json == 'IsoReps' and unit_of_measure_from_json == 'Number':
                    isoreps_descriptor_id = metric_descriptor_entry.metric_descriptor_id
                elif metric_name_from_json == 'Level' and unit_of_measure_from_json == 'Number': # Identify Level descriptor
                    level_descriptor_json_index = json_i
        
        # == Workout Sample Processing ============================================
        samples_json = workout_main_container.get('analitics', {}).get('samples', [])
        last_isoreps_value = None # To store the final IsoReps count for summary
        level_data_points = [] # To store (time_offset, level_value) for average calculation
        
        for sample_json in samples_json:
            time_offset = sample_json.get('t') # Time offset for the sample
            values_from_json = sample_json.get('vs', []) # List of values, index corresponds to descriptor's 'i'
            
            # -- Collect Level Data for Averaging -------------------
            if level_descriptor_json_index is not None and \
               time_offset is not None and \
               level_descriptor_json_index < len(values_from_json):
                level_value = values_from_json[level_descriptor_json_index]
                if level_value is not None:
                    try:
                        level_data_points.append((float(time_offset), float(level_value)))
                    except (ValueError, TypeError):
                        current_app.logger.warning(f"Could not parse level data: t={time_offset}, v={level_value}")

            for original_json_index, value in enumerate(values_from_json):
                descriptor_obj = metric_descriptor_map_for_samples.get(original_json_index) # Get corresponding MetricDescriptor
                if descriptor_obj: # If a descriptor exists for this sample index
                    workout_sample = WorkoutSample(
                        workout_id=new_workout.workout_id,
                        metric_descriptor_id=descriptor_obj.metric_descriptor_id,
                        time_offset_seconds=time_offset,
                        value=value
                    )
                    db.session.add(workout_sample)
                    
                    # -- Track Last IsoReps Value -------------------
                    if descriptor_obj.metric_descriptor_id == isoreps_descriptor_id:
                        last_isoreps_value = value

        # == Workout Summary Data Population ============================================
        # -- Initialize Summary Variables ------------------
        extracted_duration_seconds = None
        calculated_total_distance_meters = None
        calculated_average_split_seconds_500m = None
        
        # -- Extract Duration from Summary Data -------------------
        summary_entries_json = workout_main_container.get('data', []) # This 'data' is different from the top-level 'data'
        for entry_json in summary_entries_json:
            property_key = entry_json.get('property')
            if property_key == 'Move': continue # Skip 'Move' property
            if property_key == 'Duration':
                try:
                    raw_duration_value = float(entry_json.get('rawValue'))
                    unit = entry_json.get('uM', '').lower()
                    # Convert duration to seconds based on unit
                    if unit in ["min", "minute", "minutes"]: extracted_duration_seconds = raw_duration_value * 60
                    elif unit in ["h", "hour", "hours"]: extracted_duration_seconds = raw_duration_value * 3600
                    elif unit in ["ms", "millisecond", "milliseconds"]: extracted_duration_seconds = raw_duration_value / 1000.0
                    elif unit in ["s", "sec", "second", "seconds"] or not unit: extracted_duration_seconds = raw_duration_value
                    if extracted_duration_seconds is not None: break # Stop if duration found
                except (ValueError, TypeError): pass # Ignore parsing errors for this field
        
        # -- Calculate Total Distance from Samples -------------------
        distance_metric_descriptor_id_to_check = None
        # Find a 'distance' metric descriptor
        for _json_idx, desc_obj_in_map in metric_descriptor_map_for_samples.items():
            if desc_obj_in_map.metric_name and 'distance' in desc_obj_in_map.metric_name.lower():
                distance_metric_descriptor_id_to_check = desc_obj_in_map.metric_descriptor_id
                break
        
        if distance_metric_descriptor_id_to_check: # If a distance descriptor was found
            # Get the last sample for this distance metric
            last_distance_sample = WorkoutSample.query.filter_by(
                workout_id=new_workout.workout_id,
                metric_descriptor_id=distance_metric_descriptor_id_to_check
            ).order_by(WorkoutSample.time_offset_seconds.desc()).first()
            if last_distance_sample and last_distance_sample.value is not None:
                calculated_total_distance_meters = float(last_distance_sample.value)
        
        # -- Fallback: Extract Distance from Summary Data if not found in samples -------------------
        if calculated_total_distance_meters is None: 
            for entry_json in summary_entries_json:
                pkey = entry_json.get('property', '').lower()
                if 'distance' in pkey:
                    try:
                        val = float(entry_json.get('rawValue'))
                        unit = entry_json.get('uM', '').lower()
                        # Convert distance to meters based on unit
                        if unit == 'km': calculated_total_distance_meters = val * 1000
                        elif unit == 'mi': calculated_total_distance_meters = val * 1609.34 # Miles to meters
                        elif unit == 'm' or not unit: calculated_total_distance_meters = val
                        if calculated_total_distance_meters is not None: break # Stop if distance found
                    except (ValueError, TypeError): pass # Ignore parsing errors
        
        # -- Calculate Average Split -------------------
        if extracted_duration_seconds is not None and calculated_total_distance_meters is not None and calculated_total_distance_meters > 0:
            calculated_average_split_seconds_500m = (extracted_duration_seconds / calculated_total_distance_meters) * 500
        
        # -- Calculate Average Level -------------------
        calculated_average_level = None
        if level_data_points and extracted_duration_seconds is not None and extracted_duration_seconds > 0:
            level_data_points.sort(key=lambda x: x[0]) # Sort by time_offset
            
            weighted_level_sum = 0.0
            last_event_time = 0.0

            for i in range(len(level_data_points)):
                current_sample_time, current_level = level_data_points[i]
                
                # Determine the level active *before* this sample's time
                # For the first segment (0 to current_sample_time), use current_level
                level_for_segment = current_level if i == 0 else level_data_points[i-1][1]
                
                duration_of_segment = current_sample_time - last_event_time
                if duration_of_segment > 0:
                    weighted_level_sum += level_for_segment * duration_of_segment
                
                last_event_time = current_sample_time

            # Account for the last level up to extracted_duration_seconds
            if level_data_points: # Ensure there was at least one sample
                last_level_value = level_data_points[-1][1]
                duration_of_last_segment = extracted_duration_seconds - last_event_time
                if duration_of_last_segment > 0:
                    weighted_level_sum += last_level_value * duration_of_last_segment
            
            if extracted_duration_seconds > 0: # Avoid division by zero
                 calculated_average_level = weighted_level_sum / extracted_duration_seconds
            elif level_data_points: # If duration is 0 but samples exist, take the first level
                calculated_average_level = level_data_points[0][1]

        # -- Update Workout Object with Summary Data -------------------
        new_workout.duration_seconds = extracted_duration_seconds
        new_workout.total_distance_meters = calculated_total_distance_meters
        new_workout.average_split_seconds_500m = calculated_average_split_seconds_500m
        new_workout.total_isoreps = last_isoreps_value # Set total IsoReps from last sample
        new_workout.level = calculated_average_level # Set calculated average level

        # == Heart Rate Data Processing ============================================
        # -- Process HeartRateSamples -------------------
        # Look for HR samples in various possible locations in the JSON
        hr_samples_json = json_data.get('hr', workout_main_container.get('hr', workout_main_container.get('analitics', {}).get('hr', [])))
        if hr_samples_json:
            for hr_item in hr_samples_json:
                if hr_item.get('hr') is not None: # Ensure HR value exists
                    db.session.add(HeartRateSample(workout_id=new_workout.workout_id, time_offset_seconds=hr_item.get('t'), heart_rate_bpm=hr_item.get('hr')))
        
        # -- Process WorkoutHRZones -------------------
        # Look for HR zones in various possible locations in the JSON
        hr_zones_json = json_data.get('hrZones', workout_main_container.get('hrZones', workout_main_container.get('analitics', {}).get('hrZones', [])))
        if hr_zones_json:
            for zone_item in hr_zones_json:
                db.session.add(WorkoutHRZone(
                    workout_id=new_workout.workout_id, 
                    zone_name=zone_item.get('name'), 
                    color_hex=zone_item.get('color'), 
                    lower_bound_bpm=zone_item.get('lowerBound'), 
                    upper_bound_bpm=zone_item.get('upperBound'), 
                    seconds_in_zone=zone_item.get('secondsInZone')
                ))

        # == Finalize Transaction ============================================
        db.session.commit() # Commit all changes to the database
        flash('Workout data submitted successfully!', 'success')
        return redirect(url_for('home')) # Redirect to home page on success

    except IntegrityError as e: # Handle database integrity violations (e.g., unique constraints)
        db.session.rollback()
        current_app.logger.error(f"IntegrityError during workout submission: {e.orig}", exc_info=True)
        flash(f'Database integrity error: {str(e.orig)}. Could not submit workout.', 'danger')
    except Exception as e: # Catch any other exceptions during processing
        db.session.rollback()
        current_app.logger.error(f'Error submitting workout: {e}', exc_info=True)
        flash(f'Error submitting workout: {str(e)}', 'danger')
    
    return redirect(url_for('home')) # Redirect to home on failure

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the JSON workout submission route with the Flask application
def register_routes(app):
    app.add_url_rule('/submit_json_workout', endpoint='submit_json_workout', view_func=submit_json_workout, methods=['POST'])