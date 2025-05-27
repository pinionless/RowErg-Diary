# ========================================================
# = home.py - View for the home page
# ========================================================
from flask import render_template, current_app
from models import db, Workout, MetricDescriptor, WorkoutSample # Ensure all are imported
from sqlalchemy import desc
import json

# --------------------------------------------------------
# - Home View Function
#---------------------------------------------------------
# Displays the home page with the latest five workouts.
def home():
    # == Query Latest Workouts ============================================
    # Fetch the latest five workouts, ordered by date and then ID for consistency
    latest_five_workouts = Workout.query.order_by(
        Workout.workout_date.desc(), # Order by workout date descending
        Workout.workout_id.desc() # Then by workout ID descending
    ).limit(5).all() # Limit to 5 results

    # == Prepare Data for Template ============================================
    workouts_display_data = []
    
    pace_metric_descriptor = MetricDescriptor.query.filter_by(metric_name='RowingSplit').first()
    pace_metric_id = pace_metric_descriptor.metric_descriptor_id if pace_metric_descriptor else None

    for workout_item in latest_five_workouts: # Iterate through the fetched workouts
        time_categories_json = None
        pace_series_json = None

        # Fetch chart data for each workout_item
        if pace_metric_id and workout_item.duration_seconds is not None and float(workout_item.duration_seconds) > 0:
            try:
                workout_duration_int = int(float(workout_item.duration_seconds))
                categories = list(range(workout_duration_int + 1)) # Time categories from 0 to duration
                
                samples_query = WorkoutSample.query.filter_by(
                    workout_id=workout_item.workout_id,
                    metric_descriptor_id=pace_metric_id
                ).order_by(WorkoutSample.time_offset_seconds.asc()).all()

                metric_samples_dict = {}
                for sample in samples_query:
                    try:
                        value_float = float(sample.value)
                        if value_float > 0: # Pace must be > 0 to be valid
                            metric_samples_dict[sample.time_offset_seconds] = value_float
                        else:
                            metric_samples_dict[sample.time_offset_seconds] = None # Invalid pace as None
                    except (ValueError, TypeError):
                        metric_samples_dict[sample.time_offset_seconds] = None # Parsing error as None
                
                pace_series_list = [metric_samples_dict.get(t_offset, None) for t_offset in categories]
                
                if any(val is not None for val in pace_series_list):
                    time_categories_json = json.dumps(categories)
                    pace_series_json = json.dumps(pace_series_list)
                else: # If no valid pace data, ensure JSON is 'null' for template consistency
                    time_categories_json = json.dumps(None)
                    pace_series_json = json.dumps(None)
            except Exception as e:
                current_app.logger.error(f"Error fetching chart data for workout {workout_item.workout_id} on homepage: {e}", exc_info=True)
                time_categories_json = json.dumps(None)
                pace_series_json = json.dumps(None)
        else: # No duration or no pace metric ID
            time_categories_json = json.dumps(None)
            pace_series_json = json.dumps(None)

        workouts_display_data.append({
            'workout_obj': workout_item, # Pass the raw workout object
            'name': workout_item.workout_name or "Unnamed Workout", # Include workout name for direct access in template
            'chart_time_categories': time_categories_json,
            'pace_series_data': pace_series_json
        })

    # Remove the separate latest_workout_chart_data logic as it's now per workout
    # latest_workout_chart_data = None 

    # == Render Template ============================================
    return render_template('index.html',
        workouts_display_data=workouts_display_data # Pass the augmented list of workouts
        # latest_workout_chart_data is no longer needed here
    )

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the home page route with the Flask application
def register_routes(app):
    app.add_url_rule('/', view_func=home, methods=['GET']) # Root URL for the application