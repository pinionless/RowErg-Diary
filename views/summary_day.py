# ========================================================
# = dailysummary.py - View for displaying paginated daily workout summaries
# ========================================================
from flask import render_template, redirect, url_for, current_app
from sqlalchemy import text # Import text for raw SQL execution
from models import db # Assuming db is initialized and available
from utils import CustomPagination # Import CustomPagination from utils
from datetime import datetime # Added for chart category formatting
import math # Added for chart data sanitization

# --------------------------------------------------------
# - Daily Summary View Function
#---------------------------------------------------------
# Displays paginated daily workout summaries from the mv_day_totals materialized view.
def summary_day(page_num=1):
    # == Pagination Configuration ============================================
    per_page_value = current_app.config.get('PER_PAGE', 10) # Get items per page from app config

    # == Query Total Count for Pagination ============================================
    # Get the total number of daily summary records for pagination logic.
    count_result = db.session.execute(text("SELECT COUNT(*) FROM mv_day_totals")).scalar() # Total records in mv_day_totals
    total_pages = (count_result + per_page_value - 1) // per_page_value if count_result > 0 else 1 # Calculate total pages

    # == Page Number Validation and Redirection ============================================
    # Ensure page_num is within valid bounds.
    if page_num < 1:
        page_num = 1 # Default to page 1 if page_num is less than 1
    elif page_num > total_pages and total_pages > 0: # If requested page is beyond the last page with data
        return redirect(url_for('summary_day_paginated', page_num=total_pages))
    elif page_num > total_pages and total_pages == 0: # If no data, redirect to page 1
        return redirect(url_for('summary_day_paginated', page_num=1))

    # == Calculate Offset for SQL Query ============================================
    offset = (page_num - 1) * per_page_value # Calculate the starting point for records on the current page

    # == Query Data for Current Page ============================================
    # Fetch daily summary data for the current page using LIMIT and OFFSET.
    # Data is fetched DESC for table display. A reversed copy will be used for the chart.
    dailysummary_raw_results_desc = db.session.execute(text(f"""
        SELECT
            day_date,
            total_meters_rowed,
            total_seconds_rowed,
            average_split_seconds_per_500m AS split,
            total_isoreps_sum
        FROM
            mv_day_totals
        ORDER BY
            day_date DESC
        LIMIT :limit OFFSET :offset
    """), {'limit': per_page_value, 'offset': offset}).fetchall() # Execute query with parameters

    # == Prepare Data for Template ============================================
    # Convert raw SQL results into a list of dictionaries for easier template access.
    dailysummary_display_data = []
    for row in dailysummary_raw_results_desc:
        dailysummary_display_data.append({
            'day_date': row.day_date,
            'meters': float(row.total_meters_rowed) if row.total_meters_rowed is not None else 0,
            'seconds': float(row.total_seconds_rowed) if row.total_seconds_rowed is not None else 0,
            'split': float(row.split) if row.split is not None else 0,
            'isoreps': float(row.total_isoreps_sum) if row.total_isoreps_sum is not None else 0
        })

    # == Custom Pagination Object ============================================
    # The local CustomPagination class definition that was previously here is removed.
    # We now use the CustomPagination class imported from utils.py.

    # -- Instantiate Custom Pagination Object -------------------
    dailysummary_pagination = CustomPagination(page_num, per_page_value, count_result, dailysummary_display_data)

    # == Prepare Data for Chart (from paginated results) ============================================
    # Use the paginated data (reversed for chronological order) for the chart.
    chart_data_source = list(reversed(dailysummary_raw_results_desc))

    chart_categories_dates = []
    chart_series_data_meters = []
    chart_series_data_seconds = []
    chart_series_data_pace = []
    chart_series_data_reps = []

    if chart_data_source: # Process the paginated (and reversed) data
        for row in chart_data_source:
            # Format date as "YYYY-MM-DD" or any other preferred format
            date_str = row.day_date.strftime('%Y-%m-%d')
            chart_categories_dates.append(date_str)
            
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
        'dailysummary.html',
        dailysummary_pagination=dailysummary_pagination, # Pass pagination object to template
        dailysummary_display_data=dailysummary_display_data, # Pass display data to template
        page_title="Daily Workout Summaries", 
        # Chart data
        chart_categories_dates=chart_categories_dates,
        series_data_meters=chart_series_data_meters,
        series_data_seconds=chart_series_data_seconds,
        series_data_pace=chart_series_data_pace,
        series_data_reps=chart_series_data_reps,
        has_chart_data=has_chart_data
    )

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the daily summary view routes with the Flask application.
def register_routes(app):
    app.add_url_rule('/summary_day/', endpoint='summary_day', view_func=lambda: summary_day(1), methods=['GET']) # Route for the first page
    app.add_url_rule('/summary_day/page/<int:page_num>', endpoint='summary_day_paginated', view_func=summary_day, methods=['GET']) # Route for subsequent pages