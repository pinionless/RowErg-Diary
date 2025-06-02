# ========================================================
# = workouts_by_week.py - View for displaying workouts for a specific week
# ========================================================
from flask import render_template, flash, redirect, url_for, current_app
from models import db, Workout # Workout model might not be directly needed here anymore
from sqlalchemy import text
from datetime import datetime, timedelta
import math # Added for chart data sanitization

# --------------------------------------------------------
# - Show Workouts for Specific Week View Function
#---------------------------------------------------------
# Displays a summary for a specific week, and then daily summaries for each day in that week.
# The year_week_str is expected in 'YYYY-Www' format (e.g., '2023-W35').
def show_workouts_for_week(year_week_str):
    # == Week Parsing and Validation ============================================
    try:
        year_str, week_str = year_week_str.split('-W')
        year = int(year_str)
        week_number = int(week_str)
        if not (1 <= week_number <= 53): # ISO weeks can go up to 53
            raise ValueError("Week number out of range.")
        # Monday is day 1 for fromisocalendar
        week_start_date = datetime.fromisocalendar(year, week_number, 1).date()
        week_end_date = week_start_date + timedelta(days=6) # Sunday
    except ValueError:
        flash(f'Invalid week format: {year_week_str}. Expected YYYY-Www (e.g., 2023-W35).', 'danger')
        return redirect(url_for('summary_week')) 

    # == Fetch Overall Weekly Summary from Materialized View ============================================
    week_summary_data = None
    try:
        summary_result = db.session.execute(
            text("""
                SELECT
                    total_meters_rowed,
                    total_seconds_rowed,
                    average_split_seconds_per_500m AS split,
                    total_isoreps_sum
                FROM
                    mv_week_totals
                WHERE
                    week_start_date = :selected_week_start_date
            """),
            {'selected_week_start_date': week_start_date}
        ).fetchone()

        if summary_result:
            week_summary_data = {
                'meters': float(summary_result.total_meters_rowed) if summary_result.total_meters_rowed is not None else 0,
                'seconds': float(summary_result.total_seconds_rowed) if summary_result.total_seconds_rowed is not None else 0,
                'split': float(summary_result.split) if summary_result.split is not None else 0,
                'isoreps': float(summary_result.total_isoreps_sum) if summary_result.total_isoreps_sum is not None else 0
            }
        else:
            week_summary_data = {'meters': 0, 'seconds': 0, 'split': 0, 'isoreps': 0}
            
    except Exception as e:
        current_app.logger.error(f"Error fetching weekly summary for week starting {week_start_date}: {e}", exc_info=True)
        week_summary_data = {'meters': 0, 'seconds': 0, 'split': 0, 'isoreps': 0}
        flash("Could not retrieve weekly summary statistics for the selected week.", "warning")

    # == Fetch Daily Summaries for each day in the Selected Week ============================================
    daily_summaries_in_week = []
    try:
        daily_results = db.session.execute(
            text("""
                SELECT
                    day_date,
                    total_meters_rowed,
                    total_seconds_rowed,
                    average_split_seconds_per_500m AS split,
                    total_isoreps_sum
                FROM
                    mv_day_totals
                WHERE
                    day_date >= :start_date AND day_date <= :end_date
                ORDER BY
                    day_date ASC
            """),
            {'start_date': week_start_date, 'end_date': week_end_date}
        ).fetchall()

        # Create a dictionary for quick lookup
        daily_data_map = {row.day_date: row for row in daily_results}

        # Iterate through all days of the week to ensure all days are represented
        current_day = week_start_date
        while current_day <= week_end_date:
            if current_day in daily_data_map:
                row = daily_data_map[current_day]
                daily_summaries_in_week.append({
                    'day_date': row.day_date,
                    'meters': float(row.total_meters_rowed) if row.total_meters_rowed is not None else 0,
                    'seconds': float(row.total_seconds_rowed) if row.total_seconds_rowed is not None else 0,
                    'split': float(row.split) if row.split is not None else 0,
                    'isoreps': float(row.total_isoreps_sum) if row.total_isoreps_sum is not None else 0,
                    'has_workouts': True # Indicates data came from mv_day_totals
                })
            else:
                # Add a placeholder for days with no workouts
                daily_summaries_in_week.append({
                    'day_date': current_day,
                    'meters': 0,
                    'seconds': 0,
                    'split': 0,
                    'isoreps': 0,
                    'has_workouts': False # Indicates no data in mv_day_totals
                })
            current_day += timedelta(days=1)
            
    except Exception as e:
        current_app.logger.error(f"Error fetching daily summaries for week starting {week_start_date}: {e}", exc_info=True)
        flash("Could not retrieve daily summaries for the selected week.", "warning")
        # Populate with empty days if error occurs
        daily_summaries_in_week = []
        current_day = week_start_date
        while current_day <= week_end_date:
            daily_summaries_in_week.append({
                'day_date': current_day, 'meters': 0, 'seconds': 0, 'split': 0, 'isoreps': 0, 'has_workouts': False
            })
            current_day += timedelta(days=1)

    # == Prepare Data for Chart (from daily_summaries_in_week) ============================================
    chart_categories_labels_week = []
    series_data_meters_week = []
    series_data_seconds_week = []
    series_data_pace_week = []
    series_data_reps_week = []
    has_chart_data_week = False

    if daily_summaries_in_week:
        has_chart_data_week = True
        for daily_summary in daily_summaries_in_week:
            chart_categories_labels_week.append(daily_summary['day_date'].strftime('%a, %b %d')) # Format: Mon, Jan 01
            
            meters = daily_summary.get('meters')
            seconds = daily_summary.get('seconds')
            split = daily_summary.get('split')
            reps = daily_summary.get('isoreps')

            series_data_meters_week.append(meters if isinstance(meters, (int, float)) and math.isfinite(meters) else None)
            series_data_seconds_week.append(seconds if isinstance(seconds, (int, float)) and math.isfinite(seconds) else None)
            series_data_pace_week.append(split if isinstance(split, (int, float)) and math.isfinite(split) and split > 0 else None)
            series_data_reps_week.append(reps if isinstance(reps, (int, float)) and math.isfinite(reps) and reps >= 0 else None)

    # == Render Template ============================================
    return render_template(
        'workouts_by_week.html',
        year=year,
        week_number=week_number,
        week_start_date_obj=week_start_date, # Pass date objects for potential use
        week_end_date_obj=week_end_date,     # Pass date objects for potential use
        selected_week_str=f"Week {week_number}, {year} ({week_start_date.strftime('%b %d')} - {week_end_date.strftime('%b %d, %Y')})",
        week_summary_data=week_summary_data,
        daily_summaries_in_week=daily_summaries_in_week, # Pass the list of daily summaries
        # Chart data for the week
        has_chart_data_week=has_chart_data_week,
        chart_categories_labels_week=chart_categories_labels_week,
        series_data_meters_week=series_data_meters_week,
        series_data_seconds_week=series_data_seconds_week,
        series_data_pace_week=series_data_pace_week,
        series_data_reps_week=series_data_reps_week
    )

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
def register_routes(app):
    app.add_url_rule('/workouts/week/<string:year_week_str>', 
                     endpoint='workouts_by_week_detail', 
                     view_func=show_workouts_for_week, 
                     methods=['GET'])
