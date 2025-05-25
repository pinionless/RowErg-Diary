# views/home.py
from flask import render_template
# Removed: from sqlalchemy.orm import joinedload (no longer strictly needed here for summary data)
from models import Workout
# Removed: from utils import format_duration_ms (no longer used in this file, template uses it)

# You might want a new utility function for formatting total_seconds into hh:mm:ss or d:hh:mm
# e.g., from utils import format_seconds_to_readable_time

def home():
    latest_five_workouts = Workout.query.order_by(
        Workout.workout_date.desc(),
        Workout.workout_id.desc()
    ).limit(5).all()

    # Simplified: workouts_display_data will now just be a list of Workout objects
    # The templates (index.html) will handle formatting directly using filters.
    # We still pass it as 'workouts_display_data' for consistency if the template
    # expects 'item_data.workout_obj' inside a loop.
    # Alternatively, we could just pass 'latest_five_workouts' directly and adjust the template.
    # For minimal change to the template, we'll wrap it.
    
    workouts_display_data = []
    for workout_item in latest_five_workouts:
        workouts_display_data.append({
            'workout_obj': workout_item,
            'name': workout_item.workout_name # This was already used by the template
            # The 'summary' dictionary is removed as templates format directly
        })

    return render_template('index.html',
        workouts_display_data=workouts_display_data
    )

def register_routes(app):
    app.add_url_rule('/', view_func=home, methods=['GET'])