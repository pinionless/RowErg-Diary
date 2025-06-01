# ========================================================
# = summary_week.py - View for displaying paginated weekly workout summaries
# ========================================================
from flask import render_template, redirect, url_for, current_app
from sqlalchemy import text
from models import db # Assuming db is initialized and available
from utils import CustomPagination # Import CustomPagination
from datetime import datetime # Added for chart category formatting
import math # Added for chart data sanitization

# --------------------------------------------------------
# - Weekly Summary View Function
#---------------------------------------------------------
# Displays paginated weekly workout summaries from the mv_week_totals materialized view.
def summary_week(page_num=1): # Renamed function
    # == Pagination Configuration ============================================
    per_page_value = current_app.config.get('PER_PAGE', 10) # Get items per page from app config

    # == Query Total Count for Pagination ============================================
    count_result = db.session.execute(text("SELECT COUNT(*) FROM mv_week_totals")).scalar()
    total_pages = (count_result + per_page_value - 1) // per_page_value if count_result > 0 else 1

    # == Page Number Validation and Redirection ============================================
    if page_num < 1:
        page_num = 1
    elif page_num > total_pages and total_pages > 0:
        return redirect(url_for('summary_week_paginated', page_num=total_pages)) # Updated url_for
    elif page_num > total_pages and total_pages == 0: # If no data, redirect to page 1
        return redirect(url_for('summary_week_paginated', page_num=1)) # Updated url_for

    # == Calculate Offset for SQL Query ============================================
    offset = (page_num - 1) * per_page_value

    # == Query Data for Current Page ============================================
    # Data is fetched DESC for table display. A reversed copy will be used for the chart.
    summary_week_raw_results_desc = db.session.execute(text(f"""
        SELECT
            week_start_date,
            total_meters_rowed,
            total_seconds_rowed,
            average_split_seconds_per_500m AS split,
            total_isoreps_sum
        FROM
            mv_week_totals
        ORDER BY
            week_start_date DESC
        LIMIT :limit OFFSET :offset
    """), {'limit': per_page_value, 'offset': offset}).fetchall()

    # == Prepare Data for Template ============================================
    summary_week_display_data = [] # Renamed variable
    for row in summary_week_raw_results_desc:
        iso_calendar = row.week_start_date.isocalendar()
        summary_week_display_data.append({ # Renamed variable
            'year': iso_calendar[0],
            'week_number': iso_calendar[1],
            'meters': float(row.total_meters_rowed) if row.total_meters_rowed is not None else 0,
            'seconds': float(row.total_seconds_rowed) if row.total_seconds_rowed is not None else 0,
            'split': float(row.split) if row.split is not None else 0,
            'isoreps': float(row.total_isoreps_sum) if row.total_isoreps_sum is not None else 0
        })

    # == Custom Pagination Object ============================================
    summary_week_pagination = CustomPagination(page_num, per_page_value, count_result, summary_week_display_data) # Renamed variable

    # == Prepare Data for Chart ============================================
    # Use the paginated data (reversed for chronological order) for the chart.
    chart_data_source = list(reversed(summary_week_raw_results_desc))

    chart_categories_weeks = []
    chart_series_data_meters = []
    chart_series_data_seconds = []
    chart_series_data_pace = []
    chart_series_data_reps = []

    if chart_data_source: # Process the paginated (and reversed) data
        for row in chart_data_source:
            iso_cal = row.week_start_date.isocalendar()
            # Format as "W<week_num> <Year>" e.g., "W01 2023"
            week_year_str = f"W{iso_cal[1]:02d} {iso_cal[0]}"
            chart_categories_weeks.append(week_year_str)
            
            meters = float(row.total_meters_rowed) if row.total_meters_rowed is not None else None
            seconds = float(row.total_seconds_rowed) if row.total_seconds_rowed is not None else None
            split = float(row.split) if row.split is not None else None
            isoreps = float(row.total_isoreps_sum) if row.total_isoreps_sum is not None else None

            chart_series_data_meters.append(meters if isinstance(meters, (int, float)) and math.isfinite(meters) else None)
            chart_series_data_seconds.append(seconds if isinstance(seconds, (int, float)) and math.isfinite(seconds) else None)
            chart_series_data_pace.append(split if isinstance(split, (int, float)) and math.isfinite(split) and split > 0 else None)
            chart_series_data_reps.append(isoreps if isinstance(isoreps, (int, float)) and math.isfinite(isoreps) else None)
    
    has_chart_data = bool(chart_data_source) # Chart data now depends on the paginated source


    # == Render Template ============================================
    return render_template(
        'summary_week.html', # Updated template name
        summary_week_pagination=summary_week_pagination, # Renamed variable
        summary_week_display_data=summary_week_display_data, # Renamed variable
        page_title="Weekly Workout Summaries",
        # Chart data
        chart_categories_weeks=chart_categories_weeks,
        series_data_meters=chart_series_data_meters,
        series_data_seconds=chart_series_data_seconds,
        series_data_pace=chart_series_data_pace,
        series_data_reps=chart_series_data_reps,
        has_chart_data=has_chart_data
    )

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the weekly summary view routes with the Flask application.
def register_routes(app):
    app.add_url_rule('/summary_week/', endpoint='summary_week', view_func=lambda: summary_week(1), methods=['GET']) # Updated endpoint and view_func
    app.add_url_rule('/summary_week/page/<int:page_num>', endpoint='summary_week_paginated', view_func=summary_week, methods=['GET']) # Updated endpoint and view_func