# views/workouts.py
from flask import render_template, redirect, url_for, current_app
# Removed: from sqlalchemy.orm import joinedload
from models import Workout
from utils import format_duration_ms # Assuming this is for formatting split display

# You might want a new utility function for formatting total_seconds into hh:mm:ss or d:hh:mm
# e.g., from utils import format_seconds_to_readable_time

def workouts(page_num=1):
    per_page_value = current_app.config.get('PER_PAGE', 10)

    workouts_pagination = Workout.query.order_by(
        Workout.workout_date.desc(),
        Workout.workout_id.desc()
    ).paginate(page=page_num, per_page=per_page_value, error_out=False)

    workouts_display_data = []
    for workout_item in workouts_pagination.items: # workout_item is a Workout object
        distance_display = "N/A"
        if workout_item.total_distance_meters is not None:
            distance_display = f"{workout_item.total_distance_meters:,.0f} m"

        duration_display = "N/A"
        if workout_item.duration_seconds is not None:
            # Placeholder: formatting logic for duration_seconds will be needed
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
            'summary': {
                'Distance': distance_display,
                'Duration': duration_display,
                'Split': split_display
            }
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