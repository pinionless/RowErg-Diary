# views/workouts_by_date.py
from flask import render_template, abort, flash, redirect, url_for
from models import Workout
from datetime import datetime

def show_workouts_for_date(date_str):
    """
    Displays all workouts for a specific date.
    The date_str is expected in 'YYYY-MM-DD' format.
    """
    try:
        # Convert the date string to a date object
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        # If the date string is not in the correct format or is invalid
        flash('Invalid date format provided.', 'danger')
        return redirect(url_for('dailysummary')) # Or some other appropriate redirect

    # Query workouts for the selected date
    # Order by workout_id to maintain a consistent order, 
    # assuming workouts added earlier on the same day have lower IDs.
    workouts_on_date = Workout.query.filter(
        Workout.workout_date == selected_date
    ).order_by(Workout.workout_id.asc()).all()

    if not workouts_on_date:
        # You could render the page with a "No workouts found" message
        # or flash a message and redirect. For now, let's render the page.
        pass # The template will handle the "no workouts" case

    # Prepare data for the template, similar to how index.html receives it
    # This will allow reusing the same article structure for displaying workouts
    workouts_display_data = []
    for workout_item in workouts_on_date:
        workouts_display_data.append({
            'workout_obj': workout_item,
            # 'name' can be accessed via item_data.workout_obj.workout_name in the template,
            # but keeping it consistent with home.py's structure for workouts_display_data
            'name': workout_item.workout_name 
        })

    return render_template(
        'workouts_by_date.html', # We will create this template later
        selected_date=selected_date,
        workouts_display_data=workouts_display_data,
        # You might want to pass the formatted date string for the title
        selected_date_str=selected_date.strftime('%A, %B %d, %Y') 
    )

def register_routes(app):
    # The route will take a date string in YYYY-MM-DD format
    app.add_url_rule('/workouts/date/<string:date_str>', 
                     endpoint='workouts_by_date', 
                     view_func=show_workouts_for_date, 
                     methods=['GET'])