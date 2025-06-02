# ========================================================
# = workouts_by_month.py - View for displaying workouts for a specific month
# ========================================================
from flask import render_template, flash, redirect, url_for, current_app
from models import db
from sqlalchemy import text
from datetime import datetime, timedelta
import calendar
import math # Add math for chart data sanitization

# --------------------------------------------------------
# - Show Workouts for Specific Month View Function
#---------------------------------------------------------
# Displays a summary for a specific month, then weekly and daily summaries within that month.
# The year_month_str is expected in 'YYYY-MM' format (e.g., '2023-08').
def show_workouts_for_month(year_month_str):
    # == Month Parsing and Validation ============================================
    try:
        year_str, month_str = year_month_str.split('-')
        year = int(year_str)
        month = int(month_str)
        if not (1 <= month <= 12):
            raise ValueError("Month out of range.")
        
        # Get the first and last day of the month
        month_start_date = datetime(year, month, 1).date()
        num_days_in_month = calendar.monthrange(year, month)[1]
        month_end_date = datetime(year, month, num_days_in_month).date()

    except ValueError:
        flash(f'Invalid month format: {year_month_str}. Expected YYYY-MM (e.g., 2023-08).', 'danger')
        return redirect(url_for('summary_month'))

    # == Fetch Overall Monthly Summary from Materialized View ============================================
    month_summary_data = None
    try:
        summary_result = db.session.execute(
            text("""
                SELECT
                    total_meters_rowed,
                    total_seconds_rowed,
                    average_split_seconds_per_500m AS split,
                    total_isoreps_sum
                FROM
                    mv_month_totals
                WHERE
                    year = :year AND month = :month
            """),
            {'year': year, 'month': month}
        ).fetchone()

        if summary_result:
            month_summary_data = {
                'meters': float(summary_result.total_meters_rowed) if summary_result.total_meters_rowed is not None else 0,
                'seconds': float(summary_result.total_seconds_rowed) if summary_result.total_seconds_rowed is not None else 0,
                'split': float(summary_result.split) if summary_result.split is not None else 0,
                'isoreps': float(summary_result.total_isoreps_sum) if summary_result.total_isoreps_sum is not None else 0
            }
        else:
            month_summary_data = {'meters': 0, 'seconds': 0, 'split': 0, 'isoreps': 0}
            
    except Exception as e:
        current_app.logger.error(f"Error fetching monthly summary for {year}-{month}: {e}", exc_info=True)
        month_summary_data = {'meters': 0, 'seconds': 0, 'split': 0, 'isoreps': 0}
        flash("Could not retrieve monthly summary statistics.", "warning")

    # == Fetch Weekly Summaries within the Selected Month ============================================
    # A week is included if its start date is in the month OR its end date is in the month
    # More simply, fetch weeks whose start_date is between the first day of the month's week and the last day of the month.
    
    first_day_of_month_week_start = month_start_date - timedelta(days=month_start_date.weekday())
    last_day_of_month_week_end = month_end_date + timedelta(days=(6 - month_end_date.weekday()))

    # == Determine all weeks that overlap with the selected month =================================
    all_overlapping_week_starts = []
    # Start from the Monday of the week containing the first day of the month
    current_week_iter_start = month_start_date - timedelta(days=month_start_date.weekday()) 
    
    while current_week_iter_start <= month_end_date:
        all_overlapping_week_starts.append(current_week_iter_start)
        current_week_iter_start += timedelta(days=7)

    # == Fetch Weekly Summaries from mv_week_totals for these weeks =================================
    weekly_summaries_in_month = []
    db_weekly_data_map = {} # To store data fetched from mv_week_totals

    if all_overlapping_week_starts:
        try:
            # Fetch data for all potentially relevant weeks in one go
            min_queried_week_start = all_overlapping_week_starts[0]
            max_queried_week_start = all_overlapping_week_starts[-1]

            weekly_results_from_db = db.session.execute(
                text("""
                    SELECT
                        week_start_date,
                        total_meters_rowed,
                        total_seconds_rowed,
                        average_split_seconds_per_500m AS split,
                        total_isoreps_sum
                    FROM
                        mv_week_totals
                    WHERE
                        week_start_date >= :min_wsd AND week_start_date <= :max_wsd
                """),
                {'min_wsd': min_queried_week_start, 'max_wsd': max_queried_week_start}
            ).fetchall()
            
            for row in weekly_results_from_db:
                # Only map data for weeks we've identified as overlapping
                if row.week_start_date in all_overlapping_week_starts:
                    db_weekly_data_map[row.week_start_date] = row
        except Exception as e:
            current_app.logger.error(f"Error fetching weekly summaries for month {year}-{month}: {e}", exc_info=True)
            flash("Could not retrieve some weekly summaries for the selected month.", "warning")

    # == Populate weekly_summaries_in_month, including placeholders for empty weeks =================
    for week_start_date_loop in all_overlapping_week_starts:
        iso_cal = week_start_date_loop.isocalendar()
        week_end_date_loop = week_start_date_loop + timedelta(days=6)

        if week_start_date_loop in db_weekly_data_map:
            row_data = db_weekly_data_map[week_start_date_loop]
            weekly_summaries_in_month.append({
                'week_start_date': row_data.week_start_date,
                'week_end_date_display': week_end_date_loop,
                'year': iso_cal[0],
                'week_number': iso_cal[1],
                'meters': float(row_data.total_meters_rowed) if row_data.total_meters_rowed is not None else 0,
                'seconds': float(row_data.total_seconds_rowed) if row_data.total_seconds_rowed is not None else 0,
                'split': float(row_data.split) if row_data.split is not None else 0,
                'isoreps': float(row_data.total_isoreps_sum) if row_data.total_isoreps_sum is not None else 0,
                'has_workouts': True 
            })
        else:
            # This week had no workouts in mv_week_totals, create a placeholder
            weekly_summaries_in_month.append({
                'week_start_date': week_start_date_loop,
                'week_end_date_display': week_end_date_loop,
                'year': iso_cal[0],
                'week_number': iso_cal[1],
                'meters': 0,
                'seconds': 0,
                'split': 0,
                'isoreps': 0,
                'has_workouts': False 
            })

    # == Fetch Daily Summaries for each day in the Selected Month ============================================
    daily_summaries_in_month = []
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
            {'start_date': month_start_date, 'end_date': month_end_date}
        ).fetchall()

        daily_data_map = {row.day_date: row for row in daily_results}
        current_day = month_start_date
        while current_day <= month_end_date:
            if current_day in daily_data_map:
                row = daily_data_map[current_day]
                daily_summaries_in_month.append({
                    'day_date': row.day_date,
                    'meters': float(row.total_meters_rowed) if row.total_meters_rowed is not None else 0,
                    'seconds': float(row.total_seconds_rowed) if row.total_seconds_rowed is not None else 0,
                    'split': float(row.split) if row.split is not None else 0,
                    'isoreps': float(row.total_isoreps_sum) if row.total_isoreps_sum is not None else 0,
                    'has_workouts': True
                })
            else:
                daily_summaries_in_month.append({
                    'day_date': current_day, 'meters': 0, 'seconds': 0, 'split': 0, 'isoreps': 0, 'has_workouts': False
                })
            current_day += timedelta(days=1)
            
    except Exception as e:
        current_app.logger.error(f"Error fetching daily summaries for month {year}-{month}: {e}", exc_info=True)
        flash("Could not retrieve daily summaries for the selected month.", "warning")
        daily_summaries_in_month = [] # Clear if error
        current_day = month_start_date
        while current_day <= month_end_date: # Still provide day structure
            daily_summaries_in_month.append({
                'day_date': current_day, 'meters': 0, 'seconds': 0, 'split': 0, 'isoreps': 0, 'has_workouts': False
            })
            current_day += timedelta(days=1)

    # == Prepare Data for Weekly Trends Chart (from weekly_summaries_in_month) ========================
    chart_categories_labels_weekly_month = []
    series_data_meters_weekly_month = []
    series_data_seconds_weekly_month = []
    series_data_pace_weekly_month = []
    series_data_reps_weekly_month = []
    has_chart_data_weekly_trends_month = False

    if weekly_summaries_in_month:
        has_chart_data_weekly_trends_month = True
        for weekly_summary in weekly_summaries_in_month:
            chart_categories_labels_weekly_month.append(f"W{weekly_summary['week_number']:02d} '{str(weekly_summary['year'])[2:]}") # Format: W35 '23
            
            meters = weekly_summary.get('meters')
            seconds = weekly_summary.get('seconds')
            split = weekly_summary.get('split')
            reps = weekly_summary.get('isoreps')

            series_data_meters_weekly_month.append(meters if isinstance(meters, (int, float)) and math.isfinite(meters) else None)
            series_data_seconds_weekly_month.append(seconds if isinstance(seconds, (int, float)) and math.isfinite(seconds) else None)
            series_data_pace_weekly_month.append(split if isinstance(split, (int, float)) and math.isfinite(split) and split > 0 else None)
            series_data_reps_weekly_month.append(reps if isinstance(reps, (int, float)) and math.isfinite(reps) and reps >= 0 else None)

    # == Prepare Data for Daily Trends Chart (from daily_summaries_in_month) ==========================
    chart_categories_labels_daily_month = []
    series_data_meters_daily_month = []
    series_data_seconds_daily_month = []
    series_data_pace_daily_month = []
    series_data_reps_daily_month = []
    has_chart_data_daily_trends_month = False

    if daily_summaries_in_month:
        has_chart_data_daily_trends_month = True
        for daily_summary in daily_summaries_in_month:
            chart_categories_labels_daily_month.append(daily_summary['day_date'].strftime('%d %a')) # Format: 01 Mon
            
            meters = daily_summary.get('meters')
            seconds = daily_summary.get('seconds')
            split = daily_summary.get('split')
            reps = daily_summary.get('isoreps')

            series_data_meters_daily_month.append(meters if isinstance(meters, (int, float)) and math.isfinite(meters) else None)
            series_data_seconds_daily_month.append(seconds if isinstance(seconds, (int, float)) and math.isfinite(seconds) else None)
            series_data_pace_daily_month.append(split if isinstance(split, (int, float)) and math.isfinite(split) and split > 0 else None)
            series_data_reps_daily_month.append(reps if isinstance(reps, (int, float)) and math.isfinite(reps) and reps >= 0 else None)


    # == Render Template ============================================
    return render_template(
        'workouts_by_month.html',
        year=year,
        month=month,
        selected_month_str=month_start_date.strftime('%B %Y'),
        month_summary_data=month_summary_data,
        weekly_summaries_in_month=weekly_summaries_in_month,
        daily_summaries_in_month=daily_summaries_in_month,
        # Weekly trends chart data
        has_chart_data_weekly_trends_month=has_chart_data_weekly_trends_month,
        chart_categories_labels_weekly_month=chart_categories_labels_weekly_month,
        series_data_meters_weekly_month=series_data_meters_weekly_month,
        series_data_seconds_weekly_month=series_data_seconds_weekly_month,
        series_data_pace_weekly_month=series_data_pace_weekly_month,
        series_data_reps_weekly_month=series_data_reps_weekly_month,
        # Daily trends chart data for the month
        has_chart_data_daily_trends_month=has_chart_data_daily_trends_month,
        chart_categories_labels_daily_month=chart_categories_labels_daily_month,
        series_data_meters_daily_month=series_data_meters_daily_month,
        series_data_seconds_daily_month=series_data_seconds_daily_month,
        series_data_pace_daily_month=series_data_pace_daily_month,
        series_data_reps_daily_month=series_data_reps_daily_month
    )

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
def register_routes(app):
    app.add_url_rule('/workouts/month/<string:year_month_str>', 
                     endpoint='workouts_by_month_detail', 
                     view_func=show_workouts_for_month, 
                     methods=['GET'])
