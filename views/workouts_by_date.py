# ========================================================
# = workouts_by_date.py - View for displaying workouts for a specific date
# ========================================================
from flask import render_template, abort, flash, redirect, url_for, current_app
from models import db, Workout 
from sqlalchemy import text
from datetime import datetime
import math # Added for chart data sanitization
# import json # Removed json import as it's no longer needed for chart data

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

    # == Prepare Workout Data for Template =================================
    workouts_display_data = []
    
    for workout_item in workouts_on_date:
        workouts_display_data.append({
            'workout_obj': workout_item
            # Removed redundant 'name': workout_item.workout_name
        })

    # == Prepare Data for Chart (from workouts_on_date) ============================================
    chart_categories_labels = []
    chart_series_data_meters = []
    chart_series_data_seconds = []
    chart_series_data_pace = []
    chart_series_data_reps = []

    if workouts_on_date:
        for workout_item in workouts_on_date: # workouts_on_date is already ordered chronologically by ID
            label = f"{workout_item.workout_name or 'Workout'} (ID:{workout_item.workout_id})"
            chart_categories_labels.append(label)

            meters = float(workout_item.total_distance_meters) if workout_item.total_distance_meters is not None else None
            seconds = float(workout_item.duration_seconds) if workout_item.duration_seconds is not None else None
            split = float(workout_item.average_split_seconds_500m) if workout_item.average_split_seconds_500m is not None else None
            reps = float(workout_item.total_isoreps) if workout_item.total_isoreps is not None else None

            chart_series_data_meters.append(meters if isinstance(meters, (int, float)) and math.isfinite(meters) else None)
            chart_series_data_seconds.append(seconds if isinstance(seconds, (int, float)) and math.isfinite(seconds) else None)
            chart_series_data_pace.append(split if isinstance(split, (int, float)) and math.isfinite(split) and split > 0 else None)
            chart_series_data_reps.append(reps if isinstance(reps, (int, float)) and math.isfinite(reps) and reps >= 0 else None)
    
    has_chart_data = bool(workouts_on_date)

    # == Render Template ============================================
    return render_template(
        'workouts_by_date.html',
        selected_date=selected_date, # Pass the date object
        selected_date_str=selected_date.strftime('%A, %B %d, %Y'), # Pass formatted date string
        daily_summary_data=daily_summary_data, # Pass daily summary statistics
        workouts_display_data=workouts_display_data, # Pass list of workouts for the day
        # Chart data
        chart_categories_labels=chart_categories_labels, # Changed from chart_categories_dates
        series_data_meters=chart_series_data_meters,
        series_data_seconds=chart_series_data_seconds,
        series_data_pace=chart_series_data_pace,
        series_data_reps=chart_series_data_reps,
        has_chart_data=has_chart_data
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