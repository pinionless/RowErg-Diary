# ========================================================
# = workouts_by_year.py - View for displaying workout details for a specific year
# ========================================================
from flask import render_template, flash, redirect, url_for, current_app
from models import db
from sqlalchemy import text
from datetime import datetime, timedelta
import calendar

# --------------------------------------------------------
# - Show Workouts for Specific Year View Function
#---------------------------------------------------------
# Displays a summary for a specific year, then monthly and weekly summaries within that year.
# The year_param is expected as a string (e.g., '2023').
def show_workouts_for_year(year_param):
    # == Year Parsing and Validation ============================================
    try:
        year = int(year_param)
        # Define start and end dates for the year
        year_start_date = datetime(year, 1, 1).date()
        year_end_date = datetime(year, 12, 31).date()
    except ValueError:
        flash(f'Invalid year format: {year_param}. Expected YYYY (e.g., 2023).', 'danger')
        return redirect(url_for('yearlysummary'))

    # == Fetch Overall Yearly Summary from Materialized View ============================================
    year_summary_data = None
    try:
        summary_result = db.session.execute(
            text("""
                SELECT
                    total_meters_rowed,
                    total_seconds_rowed,
                    average_split_seconds_per_500m AS split,
                    total_isoreps_sum
                FROM
                    mv_year_totals
                WHERE
                    year = :selected_year
            """),
            {'selected_year': year}
        ).fetchone()

        if summary_result:
            year_summary_data = {
                'meters': float(summary_result.total_meters_rowed) if summary_result.total_meters_rowed is not None else 0,
                'seconds': float(summary_result.total_seconds_rowed) if summary_result.total_seconds_rowed is not None else 0,
                'split': float(summary_result.split) if summary_result.split is not None else 0,
                'isoreps': float(summary_result.total_isoreps_sum) if summary_result.total_isoreps_sum is not None else 0
            }
        else:
            year_summary_data = {'meters': 0, 'seconds': 0, 'split': 0, 'isoreps': 0}
            
    except Exception as e:
        current_app.logger.error(f"Error fetching yearly summary for {year}: {e}", exc_info=True)
        year_summary_data = {'meters': 0, 'seconds': 0, 'split': 0, 'isoreps': 0}
        flash("Could not retrieve yearly summary statistics.", "warning")

    # == Fetch Monthly Summaries for the Selected Year ============================================
    monthly_summaries_in_year = []
    db_monthly_data_map = {}
    try:
        monthly_results_from_db = db.session.execute(
            text("""
                SELECT
                    month,
                    total_meters_rowed,
                    total_seconds_rowed,
                    average_split_seconds_per_500m AS split,
                    total_isoreps_sum
                FROM
                    mv_month_totals
                WHERE
                    year = :selected_year
                ORDER BY
                    month ASC
            """),
            {'selected_year': year}
        ).fetchall()
        for row in monthly_results_from_db:
            db_monthly_data_map[int(row.month)] = row
            
    except Exception as e:
        current_app.logger.error(f"Error fetching monthly summaries for year {year}: {e}", exc_info=True)
        flash("Could not retrieve monthly summaries for the selected year.", "warning")

    for month_num in range(1, 13):
        month_name_str = datetime(year, month_num, 1).strftime('%B')
        if month_num in db_monthly_data_map:
            row_data = db_monthly_data_map[month_num]
            monthly_summaries_in_year.append({
                'year': year,
                'month': month_num,
                'month_name': month_name_str,
                'meters': float(row_data.total_meters_rowed) if row_data.total_meters_rowed is not None else 0,
                'seconds': float(row_data.total_seconds_rowed) if row_data.total_seconds_rowed is not None else 0,
                'split': float(row_data.split) if row_data.split is not None else 0,
                'isoreps': float(row_data.total_isoreps_sum) if row_data.total_isoreps_sum is not None else 0,
                'has_workouts': True
            })
        else:
            monthly_summaries_in_year.append({
                'year': year, 'month': month_num, 'month_name': month_name_str,
                'meters': 0, 'seconds': 0, 'split': 0, 'isoreps': 0, 'has_workouts': False
            })

    # == Fetch Weekly Summaries for the Selected Year ============================================
    # Identify all ISO weeks that overlap with the year
    all_overlapping_week_starts_for_year = []
    # Start from the Monday of the week containing Jan 1st
    current_week_iter_start_for_year = year_start_date - timedelta(days=year_start_date.weekday())
    
    while current_week_iter_start_for_year <= year_end_date:
        all_overlapping_week_starts_for_year.append(current_week_iter_start_for_year)
        current_week_iter_start_for_year += timedelta(days=7)

    weekly_summaries_in_year = []
    db_weekly_data_map_for_year = {}

    if all_overlapping_week_starts_for_year:
        try:
            min_queried_week_start_yr = all_overlapping_week_starts_for_year[0]
            max_queried_week_start_yr = all_overlapping_week_starts_for_year[-1]

            weekly_results_from_db_yr = db.session.execute(
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
                {'min_wsd': min_queried_week_start_yr, 'max_wsd': max_queried_week_start_yr}
            ).fetchall()
            
            for row in weekly_results_from_db_yr:
                if row.week_start_date in all_overlapping_week_starts_for_year:
                     db_weekly_data_map_for_year[row.week_start_date] = row
        except Exception as e:
            current_app.logger.error(f"Error fetching weekly summaries for year {year}: {e}", exc_info=True)
            flash("Could not retrieve some weekly summaries for the selected year.", "warning")

    for week_start_dt_loop_yr in all_overlapping_week_starts_for_year:
        iso_cal_yr = week_start_dt_loop_yr.isocalendar()
        week_end_dt_loop_yr = week_start_dt_loop_yr + timedelta(days=6)

        # Ensure the week is primarily within the target year for display logic
        # (e.g. week 53 of previous year might start in Dec but belong to current year by ISO rules)
        # Or week 1 of next year might start in current year.
        # We are interested in weeks that have ANY day in the current year.
        # The all_overlapping_week_starts_for_year logic already handles this.

        if week_start_dt_loop_yr in db_weekly_data_map_for_year:
            row_data_yr = db_weekly_data_map_for_year[week_start_dt_loop_yr]
            weekly_summaries_in_year.append({
                'week_start_date': row_data_yr.week_start_date,
                'week_end_date_display': week_end_dt_loop_yr,
                'year': iso_cal_yr[0], # This might be prev/next year for weeks straddling year boundary
                'week_number': iso_cal_yr[1],
                'meters': float(row_data_yr.total_meters_rowed) if row_data_yr.total_meters_rowed is not None else 0,
                'seconds': float(row_data_yr.total_seconds_rowed) if row_data_yr.total_seconds_rowed is not None else 0,
                'split': float(row_data_yr.split) if row_data_yr.split is not None else 0,
                'isoreps': float(row_data_yr.total_isoreps_sum) if row_data_yr.total_isoreps_sum is not None else 0,
                'has_workouts': True 
            })
        else:
            weekly_summaries_in_year.append({
                'week_start_date': week_start_dt_loop_yr,
                'week_end_date_display': week_end_dt_loop_yr,
                'year': iso_cal_yr[0],
                'week_number': iso_cal_yr[1],
                'meters': 0, 'seconds': 0, 'split': 0, 'isoreps': 0, 'has_workouts': False
            })
            
    # == Render Template ============================================
    return render_template(
        'workouts_by_year.html',
        selected_year_str=str(year),
        year_summary_data=year_summary_data,
        monthly_summaries_in_year=monthly_summaries_in_year,
        weekly_summaries_in_year=weekly_summaries_in_year
    )

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
def register_routes(app):
    app.add_url_rule('/workouts/year/<string:year_param>', 
                     endpoint='workouts_by_year_detail', 
                     view_func=show_workouts_for_year, 
                     methods=['GET'])
