# ========================================================
# = workouts.py - View for displaying paginated workouts
# ========================================================
from flask import render_template, redirect, url_for, current_app
from models import Workout, UserSetting # Added UserSetting
import datetime # Added for chart category formatting
import math # Added for chart data sanitization

# --------------------------------------------------------
# - Workouts View Function
#---------------------------------------------------------
# Displays a paginated list of workouts
def workouts(page_num=1):
    # == Pagination Configuration ============================================
    # Fetch 'per_page_workouts' from UserSetting table
    per_page_setting = UserSetting.query.filter_by(key='per_page_workouts').first()
    if per_page_setting and per_page_setting.value and per_page_setting.value.isdigit():
        per_page_value = int(per_page_setting.value)
        if per_page_value <= 0: # Ensure positive value
            per_page_value = 20 # Fallback to a sensible default
            current_app.logger.warning("per_page_workouts setting is not positive, using default 20.")
    else:
        per_page_value = 20 # Default if setting not found or invalid
        if per_page_setting: # Log if found but invalid
            current_app.logger.warning(f"per_page_workouts setting '{per_page_setting.value}' is invalid, using default 20.")
        else: # Log if not found
            current_app.logger.info("per_page_workouts setting not found, using default 20.")


    # == Query Workouts ============================================
    # Fetch workouts, ordered by date and ID, paginated
    workouts_pagination = Workout.query.order_by(
        Workout.workout_date.desc(), # Order by workout date descending
        Workout.workout_id.desc() # Then by workout ID descending for consistent ordering
    ).paginate(page=page_num, per_page=per_page_value, error_out=False) # Paginate results

    # == Prepare Data for Template ============================================
    # The template will directly use workout objects and Jinja filters for formatting
    workouts_for_display = workouts_pagination.items
    
    workouts_display_data = []
    for workout_item in workouts_for_display: # Iterate through paginated workout items
        workouts_display_data.append({
            'workout_obj': workout_item # Pass the raw workout object to the template
        })

    # == Prepare Data for Chart (from paginated results) ============================================
    # Use the paginated data (reversed for chronological order) for the chart.
    chart_data_source = list(reversed(workouts_for_display)) # Reverse for chronological chart

    chart_categories_dates = []
    chart_series_data_meters = []
    chart_series_data_seconds = []
    chart_series_data_pace = []
    chart_series_data_reps = [] # Initialize reps data list

    if chart_data_source:
        for workout_item in chart_data_source:
            date_str = workout_item.workout_date.strftime('%Y-%m-%d') if workout_item.workout_date else "Unknown Date"
            chart_categories_dates.append(f"{date_str} (ID:{workout_item.workout_id})")

            meters = float(workout_item.total_distance_meters) if workout_item.total_distance_meters is not None else None
            seconds = float(workout_item.duration_seconds) if workout_item.duration_seconds is not None else None
            split = float(workout_item.average_split_seconds_500m) if workout_item.average_split_seconds_500m is not None else None
            reps = float(workout_item.total_isoreps) if workout_item.total_isoreps is not None else None # Get reps data

            chart_series_data_meters.append(meters if isinstance(meters, (int, float)) and math.isfinite(meters) else None)
            chart_series_data_seconds.append(seconds if isinstance(seconds, (int, float)) and math.isfinite(seconds) else None)
            chart_series_data_pace.append(split if isinstance(split, (int, float)) and math.isfinite(split) and split > 0 else None)
            chart_series_data_reps.append(reps if isinstance(reps, (int, float)) and math.isfinite(reps) and reps >= 0 else None) # Add reps to its series
    
    has_chart_data = bool(chart_data_source)

    # == Handle Empty Page Redirects ============================================
    # If the current page is empty and not the first page, redirect to the last valid page or first page
    if not workouts_pagination.items and page_num > 1 and workouts_pagination.pages > 0 :
        return redirect(url_for('workouts_paginated', page_num=workouts_pagination.pages)) # Redirect to last page with items
    elif not workouts_pagination.items and page_num > 1 and workouts_pagination.pages == 0: # Should ideally not happen if page_num > 1
        return redirect(url_for('workouts_paginated', page_num=1)) # Redirect to first page if no pages exist (edge case)

    # == Render Template ============================================
    return render_template(
        'workouts.html',
        workouts_pagination=workouts_pagination, # Pass pagination object
        workouts_display_data=workouts_display_data, # Pass prepared workout data
        # Chart data
        chart_categories_dates=chart_categories_dates,
        series_data_meters=chart_series_data_meters,
        series_data_seconds=chart_series_data_seconds,
        series_data_pace=chart_series_data_pace,
        series_data_reps=chart_series_data_reps, # Pass reps data to template
        has_chart_data=has_chart_data
    )

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the workout view routes with the Flask application
def register_routes(app):
    app.add_url_rule('/workouts/', endpoint='workouts', view_func=lambda: workouts(1), methods=['GET']) # Route for the first page of workouts
    app.add_url_rule('/workouts/page/<int:page_num>', endpoint='workouts_paginated', view_func=workouts, methods=['GET']) # Route for subsequent paginated workout pages