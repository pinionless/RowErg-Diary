# views/submit_json_workout.py
import json
import uuid
from flask import request, redirect, url_for, flash, current_app # Use current_app for logger if needed
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from models import db, EquipmentType, PhysicalActivity, Workout, MetricDescriptor, WorkoutSample, HeartRateSample, WorkoutHRZone, WorkoutSummaryData
from utils import format_duration_ms # Import from utils

def submit_json_workout():
    raw_json_data = request.form.get('jsonData')
    if not raw_json_data:
        flash('No JSON data provided.', 'danger')
        return redirect(url_for('home')) # Assumes homepage endpoint is 'home'

    try:
        json_data = json.loads(raw_json_data)
    except json.JSONDecodeError:
        flash('Invalid JSON format.', 'danger')
        return redirect(url_for('home'))

    try:
        # ... (Your entire submission logic from the original app.py)
        # Make sure to use url_for with correct endpoint names
        # e.g., url_for('details', workout_id=new_workout.workout_id)
        # and url_for('home')

        workout_main_container = json_data.get('data', {})
        if not workout_main_container:
            flash('Main "data" object is missing or empty in the submitted JSON.', 'danger')
            return redirect(url_for('home'))

        equipment_name = workout_main_container.get('equipmentType')
        equipment_type = None
        if equipment_name:
            equipment_type = EquipmentType.query.filter_by(name=equipment_name).first()
            if not equipment_type:
                equipment_type = EquipmentType(name=equipment_name)
                db.session.add(equipment_type)
                db.session.flush()

        pa_guid_str = workout_main_container.get('physicalActivityId')
        pa_name = workout_main_container.get('physicalActivityName')
        physical_activity = None
        if pa_guid_str and pa_name:
            try:
                pa_guid = uuid.UUID(pa_guid_str)
                physical_activity = PhysicalActivity.query.get(pa_guid)
                if not physical_activity:
                    physical_activity = PhysicalActivity(physical_activity_guid=pa_guid, name=pa_name)
                    db.session.add(physical_activity)
                    db.session.flush()
            except ValueError:
                flash(f"Invalid Physical Activity GUID: {pa_guid_str}", "danger")

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

        new_workout = Workout(
            cardio_log_id=cardio_log_id,
            equipment_type_id=equipment_type.equipment_type_id if equipment_type else None,
            workout_name=workout_main_container.get('name'),
            workout_date=workout_date_obj,
            target_description=workout_main_container.get('target'),
            is_favorite=bool(workout_main_container.get('favorite', 0)),
            physical_activity_guid=physical_activity.physical_activity_guid if physical_activity else None,
            n_eser=workout_main_container.get('nEser'),
            n_attr=workout_main_container.get('nAttr'),
            imported_at=datetime.now(timezone.utc)
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

        summary_entries_json = workout_main_container.get('data', [])
        original_summary_data_objects = []
        for entry_json in summary_entries_json:
            summary_data = WorkoutSummaryData(
                workout_id=new_workout.workout_id,
                property_key=entry_json.get('property'),
                display_name=entry_json.get('name'),
                value_text=entry_json.get('value'),
                unit_of_measure=entry_json.get('uM'),
                raw_value=entry_json.get('rawValue')
            )
            db.session.add(summary_data)
            original_summary_data_objects.append(summary_data)
        
        db.session.flush()

        total_distance_meters = None
        total_duration_seconds_for_split = None

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
                total_distance_meters = float(last_distance_sample.value)
                if not WorkoutSummaryData.query.filter_by(workout_id=new_workout.workout_id, property_key='derivedTotalDistance').first():
                    dist_summary = WorkoutSummaryData(
                        workout_id=new_workout.workout_id,
                        property_key='derivedTotalDistance',
                        display_name='Total Distance (Derived)',
                        value_text=f"{total_distance_meters:.0f} m",
                        unit_of_measure='m',
                        raw_value=total_distance_meters
                    )
                    db.session.add(dist_summary)

        duration_keys_for_split = ["duration", "totaltime", "elapsedtime", "workoutduration", "totalduration"]
        for item in original_summary_data_objects:
            if item.property_key and item.property_key.lower() in duration_keys_for_split:
                try:
                    raw_duration_value = float(item.raw_value)
                    unit_of_measure = item.unit_of_measure.lower() if item.unit_of_measure else ""
                    if unit_of_measure in ["min", "minute", "minutes"]:
                        total_duration_seconds_for_split = raw_duration_value * 60
                    elif unit_of_measure in ["s", "sec", "second", "seconds"] or not unit_of_measure:
                        total_duration_seconds_for_split = raw_duration_value
                    else: continue
                    if total_duration_seconds_for_split is not None: break
                except (ValueError, TypeError): pass
        
        if total_duration_seconds_for_split is not None and total_distance_meters is not None and total_distance_meters > 0:
            split_seconds_per_500m = (total_duration_seconds_for_split / total_distance_meters) * 500
            formatted_split = format_duration_ms(split_seconds_per_500m) # Use imported function
            if not WorkoutSummaryData.query.filter_by(workout_id=new_workout.workout_id, property_key='derivedSplit500m').first():
                split_summary = WorkoutSummaryData(
                    workout_id=new_workout.workout_id,
                    property_key='derivedSplit500m',
                    display_name='Avg Split /500m (Derived)',
                    value_text=formatted_split,
                    unit_of_measure='/500m',
                    raw_value=split_seconds_per_500m
                )
                db.session.add(split_summary)
        else:
            if not WorkoutSummaryData.query.filter_by(workout_id=new_workout.workout_id, property_key='derivedSplit500m').first():
                split_summary_na = WorkoutSummaryData(
                    workout_id=new_workout.workout_id,
                    property_key='derivedSplit500m',
                    display_name='Avg Split /500m (Derived)',
                    value_text='N/A',
                    unit_of_measure='/500m',
                    raw_value=None
                )
                db.session.add(split_summary_na)

        db.session.commit()
        flash('Workout data submitted successfully!', 'success')
        return redirect(url_for('details', workout_id=new_workout.workout_id))


    except IntegrityError as e:
        db.session.rollback()
        flash(f'Database integrity error: {str(e.orig)}. Perhaps this workout already exists?', 'danger')
    except Exception as e:
        db.session.rollback()
        # Use current_app.logger.error for better logging in production
        current_app.logger.error(f'Error submitting workout: {e}', exc_info=True)
        flash(f'Error submitting workout: {str(e)}', 'danger')
    
    return redirect(url_for('home'))


def register_routes(app):
    app.add_url_rule('/submit_json_workout', endpoint='submit_json_workout', view_func=submit_json_workout, methods=['POST'])