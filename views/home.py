# views/home.py
from flask import render_template
# Removed: from sqlalchemy.orm import joinedload (no longer strictly needed here for summary data)
from models import Workout
from utils import format_duration_ms # Assuming this is for formatting split display

# You might want a new utility function for formatting total_seconds into hh:mm:ss or d:hh:mm
# e.g., from utils import format_seconds_to_readable_time

def home():
    latest_five_workouts = Workout.query.order_by(
        Workout.workout_date.desc(),
        Workout.workout_id.desc()
    ).limit(5).all()

    workouts_display_data = []
    for workout_item in latest_five_workouts:
        # Prepare summary values for display
        # These will need to be formatted in the template or by utility functions
        
        distance_display = "N/A"
        if workout_item.total_distance_meters is not None:
            distance_display = f"{workout_item.total_distance_meters:,.0f} m"

        duration_display = "N/A"
        if workout_item.duration_seconds is not None:
            # Placeholder: formatting logic for duration_seconds will be needed
            # For example, using a utility function:
            # duration_display = format_seconds_to_readable_time(workout_item.duration_seconds)
            # For now, just pass seconds and format in template or make a simple hh:mm:ss
            # This is a simple example, a robust function is better
            hours = int(workout_item.duration_seconds // 3600)
            minutes = int((workout_item.duration_seconds % 3600) // 60)
            seconds = int(workout_item.duration_seconds % 60)
            if hours > 0:
                duration_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                duration_display = f"{minutes:02d}:{seconds:02d}"


        split_display = "N/A"
        if workout_item.average_split_seconds_500m is not None:
            split_display = format_duration_ms(workout_item.average_split_seconds_500m)
        
        workouts_display_data.append({
            'workout_obj': workout_item,
            'name': workout_item.workout_name, # This was already there
            'summary': {
                'Distance': distance_display,
                'Duration': duration_display,
                'Split': split_display
            }
        })

    return render_template('index.html',
        workouts_display_data=workouts_display_data
    )

def register_routes(app):
    app.add_url_rule('/', view_func=home, methods=['GET'])