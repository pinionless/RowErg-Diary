# ========================================================
# = workouts_by_date.py - View for displaying workouts for a specific date
# ========================================================
from flask import render_template, abort, flash, redirect, url_for, current_app
from models import db, Workout, WorkoutSample, MetricDescriptor # Added WorkoutSample, MetricDescriptor
from sqlalchemy import text
from datetime import datetime
import json # To pass data to JavaScript

# --------------------------------------------------------
# - Show Workouts for Date View Function
#---------------------------------------------------------
# Displays all workouts for a specific date, along with a summary for that day.
# The date_str is expected in 'YYYY-MM-DD' format.
def show_workouts_for_date(date_str):
    # == Date Parsing and Validation ============================================
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date() # Convert string to date object
    except ValueError: # Handle invalid date format
        flash('Invalid date format provided.', 'danger')
        return redirect(url_for('dailysummary')) # Redirect if date is invalid

    # == Fetch Daily Summary from Materialized View ============================================
    daily_summary_data = None
    try:
        # -- Execute SQL Query for Daily Totals -------------------
        summary_result = db.session.execute(
            text("""
                SELECT
                    total_meters_rowed,
                    total_seconds_rowed,
                    average_split_seconds_per_500m AS split,
                    total_isoreps_sum
                FROM
                    mv_day_totals
                WHERE
                    day_date = :selected_date
            """),
            {'selected_date': selected_date} # Bind selected_date to the query
        ).fetchone()

        if summary_result: # If summary data exists for the date
            daily_summary_data = {
                'meters': float(summary_result.total_meters_rowed) if summary_result.total_meters_rowed is not None else 0,
                'seconds': float(summary_result.total_seconds_rowed) if summary_result.total_seconds_rowed is not None else 0,
                'split': float(summary_result.split) if summary_result.split is not None else 0,
                'isoreps': float(summary_result.total_isoreps_sum) if summary_result.total_isoreps_sum is not None else 0
            }
        else: # If no summary found, provide default values
            daily_summary_data = {'meters': 0, 'seconds': 0, 'split': 0, 'isoreps': 0}
            
    except Exception as e: # Handle potential database errors
        current_app.logger.error(f"Error fetching daily summary for date {selected_date}: {e}", exc_info=True)
        daily_summary_data = {'meters': 0, 'seconds': 0, 'split': 0, 'isoreps': 0} # Default on error
        flash("Could not retrieve daily summary statistics.", "warning")


    # == Fetch Individual Workouts for the Selected Date ============================================
    workouts_on_date = Workout.query.filter(
        Workout.workout_date == selected_date # Filter workouts by the selected date
    ).order_by(Workout.workout_id.asc()).all() # Order by ID for consistency

    # == Prepare Workout Data for Template, including chart data =================================
    workouts_display_data = []
    
    pace_metric_descriptor = MetricDescriptor.query.filter_by(metric_name='RowingSplit').first()
    pace_metric_id = pace_metric_descriptor.metric_descriptor_id if pace_metric_descriptor else None

    power_metric_descriptor = MetricDescriptor.query.filter_by(metric_name='Power').first() # Assuming 'Power' is the metric name
    power_metric_id = power_metric_descriptor.metric_descriptor_id if power_metric_descriptor else None

    spm_metric_descriptor = MetricDescriptor.query.filter_by(metric_name='Spm').first() # Assuming 'Spm' is the metric name for Strokes Per Minute
    spm_metric_id = spm_metric_descriptor.metric_descriptor_id if spm_metric_descriptor else None

    for workout_item in workouts_on_date:
        time_categories_json = None
        pace_series_json = None
        power_series_json = None
        spm_series_json = None

        if workout_item.duration_seconds is not None and workout_item.duration_seconds > 0:
            workout_duration_int = int(float(workout_item.duration_seconds))
            categories = list(range(workout_duration_int + 1))
            time_categories_json = json.dumps(categories)

            # Helper function to get series data for a given metric_id
            def get_series_data_for_metric(metric_id, metric_name_for_validation="Unknown"): # Added metric_name for clarity
                if not metric_id:
                    return None
                
                samples_query = WorkoutSample.query.filter_by(
                    workout_id=workout_item.workout_id,
                    metric_descriptor_id=metric_id
                ).order_by(WorkoutSample.time_offset_seconds.asc()).all()

                metric_samples_dict = {}
                for sample in samples_query:
                    try:
                        value_float = float(sample.value)
                        
                        # For Pace, value must be > 0.
                        # For Power and SPM, treat 0 as a gap (None).
                        if metric_name_for_validation == 'RowingSplit':
                            if value_float > 0:
                                metric_samples_dict[sample.time_offset_seconds] = value_float
                            else:
                                metric_samples_dict[sample.time_offset_seconds] = None
                        elif metric_name_for_validation in ['Power', 'Spm']:
                            if value_float > 0: # Changed from >= 0 to > 0
                                metric_samples_dict[sample.time_offset_seconds] = value_float
                            else: # This will now catch 0 and negative values
                                metric_samples_dict[sample.time_offset_seconds] = None
                        else: # Default for other metrics if any
                            if value_float >= 0:
                                metric_samples_dict[sample.time_offset_seconds] = value_float
                            else:
                                metric_samples_dict[sample.time_offset_seconds] = None
                    except (ValueError, TypeError):
                        metric_samples_dict[sample.time_offset_seconds] = None
                
                series_list = [metric_samples_dict.get(t_offset, None) for t_offset in categories]
                return json.dumps(series_list)

            if pace_metric_id:
                pace_series_json = get_series_data_for_metric(pace_metric_id, 'RowingSplit')
            
            if power_metric_id:
                power_series_json = get_series_data_for_metric(power_metric_id, 'Power')

            if spm_metric_id:
                spm_series_json = get_series_data_for_metric(spm_metric_id, 'Spm')
        
        workouts_display_data.append({
            'workout_obj': workout_item, 
            'name': workout_item.workout_name, 
            'chart_time_categories': time_categories_json,
            'pace_series_data': pace_series_json,
            'power_series_data': power_series_json,
            'spm_series_data': spm_series_json
        })

    # == Render Template ============================================
    return render_template(
        'workouts_by_date.html',
        selected_date=selected_date, # Pass the date object
        selected_date_str=selected_date.strftime('%A, %B %d, %Y'), # Pass formatted date string
        daily_summary_data=daily_summary_data, # Pass daily summary statistics
        workouts_display_data=workouts_display_data # Pass list of workouts for the day
    )

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the workouts by date view route with the Flask application
def register_routes(app):
    app.add_url_rule('/workouts/date/<string:date_str>', 
                     endpoint='workouts_by_date', 
                     view_func=show_workouts_for_date, 
                     methods=['GET'])