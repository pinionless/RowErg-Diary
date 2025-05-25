# views/workouts_by_date.py
from flask import render_template, abort, flash, redirect, url_for, current_app
from models import db, Workout # Added db
from sqlalchemy import text # Added text
from datetime import datetime

def show_workouts_for_date(date_str):
    """
    Displays all workouts for a specific date, along with a summary for that day.
    The date_str is expected in 'YYYY-MM-DD' format.
    """
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format provided.', 'danger')
        return redirect(url_for('dailysummary'))

    # --- Fetch Daily Summary ---
    daily_summary_data = None
    try:
        summary_result = db.session.execute(
            text("""
                SELECT
                    total_meters_rowed,
                    total_seconds_rowed,
                    average_split_seconds_per_500m AS split
                FROM
                    mv_day_totals
                WHERE
                    day_date = :selected_date
            """),
            {'selected_date': selected_date}
        ).fetchone()

        if summary_result:
            daily_summary_data = {
                'meters': float(summary_result.total_meters_rowed) if summary_result.total_meters_rowed is not None else 0,
                'seconds': float(summary_result.total_seconds_rowed) if summary_result.total_seconds_rowed is not None else 0,
                'split': float(summary_result.split) if summary_result.split is not None else 0
            }
        else:
            # If no summary found for the day (e.g., no workouts, or MV not refreshed), provide defaults
            daily_summary_data = {'meters': 0, 'seconds': 0, 'split': 0}
            
    except Exception as e:
        current_app.logger.error(f"Error fetching daily summary for date {selected_date}: {e}", exc_info=True)
        # Provide default summary data in case of error
        daily_summary_data = {'meters': 0, 'seconds': 0, 'split': 0}
        flash("Could not retrieve daily summary statistics.", "warning")


    # --- Fetch Individual Workouts ---
    workouts_on_date = Workout.query.filter(
        Workout.workout_date == selected_date
    ).order_by(Workout.workout_id.asc()).all()

    workouts_display_data = []
    for workout_item in workouts_on_date:
        workouts_display_data.append({
            'workout_obj': workout_item,
            'name': workout_item.workout_name
        })

    return render_template(
        'workouts_by_date.html',
        selected_date=selected_date,
        selected_date_str=selected_date.strftime('%A, %B %d, %Y'),
        daily_summary_data=daily_summary_data, # Pass summary to template
        workouts_display_data=workouts_display_data
    )

def register_routes(app):
    app.add_url_rule('/workouts/date/<string:date_str>', 
                     endpoint='workouts_by_date', 
                     view_func=show_workouts_for_date, 
                     methods=['GET'])