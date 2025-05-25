# views/workouts.py
from flask import render_template, redirect, url_for, current_app
# Removed: from sqlalchemy.orm import joinedload
from models import Workout
# Removed: from utils import format_duration_ms (no longer used in this file, template uses it)

# You might want a new utility function for formatting total_seconds into hh:mm:ss or d:hh:mm
# e.g., from utils import format_seconds_to_readable_time

def workouts(page_num=1):
    per_page_value = current_app.config.get('PER_PAGE', 10)

    workouts_pagination = Workout.query.order_by(
        Workout.workout_date.desc(),
        Workout.workout_id.desc()
    ).paginate(page=page_num, per_page=per_page_value, error_out=False)

    # Simplified: workouts_display_data will now just be a list of Workout objects
    # The template (workouts.html) will handle formatting directly using filters.
    # We pass it as 'workouts_display_data' and the template expects item_data.workout_obj.
    
    workouts_display_data = []
    for workout_item in workouts_pagination.items: # workout_item is a Workout object
        workouts_display_data.append({
            'workout_obj': workout_item
            # The 'summary' dictionary is removed as templates format directly
            # The workout name is accessed via item_data.workout_obj.workout_name in the template
        })

    if not workouts_pagination.items and page_num > 1 and workouts_pagination.pages > 0 :
        return redirect(url_for('workouts_paginated', page_num=workouts_pagination.pages))
    elif not workouts_pagination.items and page_num > 1 and workouts_pagination.pages == 0:
        return redirect(url_for('workouts_paginated', page_num=1))

    return render_template(
        'workouts.html',
        workouts_pagination=workouts_pagination,
        workouts_display_data=workouts_display_data
    )

def register_routes(app):
    app.add_url_rule('/workouts/', endpoint='workouts', view_func=lambda: workouts(1), methods=['GET'])
    app.add_url_rule('/workouts/page/<int:page_num>', endpoint='workouts_paginated', view_func=workouts, methods=['GET'])