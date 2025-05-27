# ========================================================
# = details.py - View for displaying detailed workout information
# ========================================================
from flask import render_template
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import distinct
from models import db, Workout, WorkoutSample, HeartRateSample, MetricDescriptor

# --------------------------------------------------------
# - Workout Details View Function
#---------------------------------------------------------
# Displays detailed information for a specific workout, including samples.
def details(workout_id):
    # == Fetch Main Workout Data ============================================
    # Retrieve the workout by ID, preloading related equipment type and HR zones
    # get_or_404 will automatically return a 404 error if the workout_id is not found.
    workout = Workout.query.options(
        joinedload(Workout.equipment_type_ref), # Eager load equipment type
        joinedload(Workout.workout_hr_zones) # Eager load heart rate zones
    ).get_or_404(workout_id)

    # == Fetch Metric Descriptors for this Workout ============================================
    # -- Get IDs of MetricDescriptors that have samples for this workout -------------------
    metric_descriptor_ids_with_samples = db.session.query(
        distinct(WorkoutSample.metric_descriptor_id) # Select unique metric_descriptor_ids
    ).filter(
        WorkoutSample.workout_id == workout_id # Filter by the current workout_id
    ).all() # Execute query and get all results
    
    # -- Extract actual IDs from the query result (list of tuples) -------------------
    actual_metric_descriptor_ids = [md_id[0] for md_id in metric_descriptor_ids_with_samples if md_id[0] is not None]

    # -- Fetch MetricDescriptor objects based on the IDs found -------------------
    workout_metric_descriptors_list = []
    if actual_metric_descriptor_ids: # If there are any metric descriptors with samples
        workout_metric_descriptors_list = MetricDescriptor.query.filter(
            MetricDescriptor.metric_descriptor_id.in_(actual_metric_descriptor_ids) # Filter by the list of IDs
        ).order_by(MetricDescriptor.metric_name).all() # Order by name for consistent display

    # == Fetch Workout Samples (Metrics) ============================================
    # -- Base query for all workout samples, ordered by time offset -------------------
    all_workout_samples_query = WorkoutSample.query.options(
        selectinload(WorkoutSample.metric_descriptor_ref) # Eager load related metric descriptor for each sample
    ).filter_by(workout_id=workout_id).order_by(WorkoutSample.time_offset_seconds.asc())
    
    total_workout_samples = all_workout_samples_query.count() # Get total count of samples
    
    # -- Logic to display first 10, last 10, and ellipsis if more than 20 samples -------------------
    first_10_workout_samples = all_workout_samples_query.limit(10).all() # Get the first 10 samples
    last_10_workout_samples = []
    workout_samples_ellipsis_needed = False
    if total_workout_samples > 10: # If more than 10 samples in total
        if total_workout_samples <= 20: # If 11-20 samples, show all remaining
            last_10_workout_samples = all_workout_samples_query.offset(10).limit(10).all()
        else: # If more than 20 samples, show ellipsis and last 10
            workout_samples_ellipsis_needed = True
            last_10_workout_samples = all_workout_samples_query.offset(total_workout_samples - 10).limit(10).all()

    # == Fetch Heart Rate Samples ============================================
    # -- Base query for all heart rate samples, ordered by time offset -------------------
    all_hr_samples_query = HeartRateSample.query.filter_by(workout_id=workout_id).order_by(HeartRateSample.time_offset_seconds.asc())
    total_hr_samples = all_hr_samples_query.count() # Get total count of HR samples
    
    # -- Logic to display first 10, last 10, and ellipsis if more than 20 HR samples -------------------
    first_10_hr_samples = all_hr_samples_query.limit(10).all() # Get the first 10 HR samples
    last_10_hr_samples = []
    hr_samples_ellipsis_needed = False
    if total_hr_samples > 10: # If more than 10 HR samples in total
        if total_hr_samples <= 20: # If 11-20 HR samples, show all remaining
            last_10_hr_samples = all_hr_samples_query.offset(10).limit(10).all()
        else: # If more than 20 HR samples, show ellipsis and last 10
            hr_samples_ellipsis_needed = True
            last_10_hr_samples = all_hr_samples_query.offset(total_hr_samples - 10).limit(10).all()
            
    # == Render Template ============================================
    # Pass all fetched and processed data to the details.html template
    return render_template(
        'details.html',
        workout=workout,
        workout_metric_descriptors=workout_metric_descriptors_list, 
        first_10_workout_samples=first_10_workout_samples,
        last_10_workout_samples=last_10_workout_samples,
        total_workout_samples=total_workout_samples,
        workout_samples_ellipsis_needed=workout_samples_ellipsis_needed,
        first_10_hr_samples=first_10_hr_samples,
        last_10_hr_samples=last_10_hr_samples,
        total_hr_samples=total_hr_samples,
        hr_samples_ellipsis_needed=hr_samples_ellipsis_needed
    )

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the workout details view route with the Flask application
def register_routes(app):
    app.add_url_rule('/details/<int:workout_id>', endpoint='details', view_func=details, methods=['GET'])