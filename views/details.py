# views/details.py
from flask import render_template
from sqlalchemy.orm import joinedload
from models import Workout, WorkoutSample, HeartRateSample

def details(workout_id):
    workout = Workout.query.options(
        joinedload(Workout.equipment_type_ref),
        joinedload(Workout.physical_activity_ref),
        joinedload(Workout.metric_descriptors).raiseload('*'),
        joinedload(Workout.workout_hr_zones),
        joinedload(Workout.workout_summary_data)
    ).get_or_404(workout_id)

    all_workout_samples_query = WorkoutSample.query.options(
        joinedload(WorkoutSample.metric_descriptor_ref)
    ).filter_by(workout_id=workout_id).order_by(WorkoutSample.time_offset_seconds.asc())
    total_workout_samples = all_workout_samples_query.count()
    
    first_10_workout_samples = all_workout_samples_query.limit(10).all()
    last_10_workout_samples = []
    workout_samples_ellipsis_needed = False
    if total_workout_samples > 10:
        if total_workout_samples <= 20:
            last_10_workout_samples = all_workout_samples_query.offset(10).limit(10).all()
        else:
            workout_samples_ellipsis_needed = True
            last_10_workout_samples = all_workout_samples_query.offset(total_workout_samples - 10).limit(10).all()


    all_hr_samples_query = HeartRateSample.query.filter_by(workout_id=workout_id).order_by(HeartRateSample.time_offset_seconds.asc())
    total_hr_samples = all_hr_samples_query.count()
    first_10_hr_samples = all_hr_samples_query.limit(10).all()
    last_10_hr_samples = []
    hr_samples_ellipsis_needed = False
    if total_hr_samples > 10:
        if total_hr_samples <= 20:
            last_10_hr_samples = all_hr_samples_query.offset(10).limit(10).all()
        else:
            hr_samples_ellipsis_needed = True
            last_10_hr_samples = all_hr_samples_query.offset(total_hr_samples - 10).limit(10).all()
            
    return render_template(
        'details.html',
        workout=workout,
        first_10_workout_samples=first_10_workout_samples,
        last_10_workout_samples=last_10_workout_samples,
        total_workout_samples=total_workout_samples,
        workout_samples_ellipsis_needed=workout_samples_ellipsis_needed,
        first_10_hr_samples=first_10_hr_samples,
        last_10_hr_samples=last_10_hr_samples,
        total_hr_samples=total_hr_samples,
        hr_samples_ellipsis_needed=hr_samples_ellipsis_needed
    )

def register_routes(app):
    app.add_url_rule('/details/<int:workout_id>', endpoint='details', view_func=details, methods=['GET'])