# ========================================================
# = summary_month.py - View for displaying paginated monthly workout summaries
# ========================================================
from flask import render_template, redirect, url_for, current_app
from sqlalchemy import text
from models import db, UserSetting # Added UserSetting
from utils import CustomPagination 
from datetime import datetime
import math # Import math for isnan and isfinite

# --------------------------------------------------------
# - Monthly Summary View Function
#---------------------------------------------------------
# Displays paginated monthly workout summaries from the mv_month_totals materialized view.
def summary_month(page_num=1): # Renamed function
    # == Pagination Configuration ============================================
    # Fetch 'per_page_summary_month' from UserSetting table
    per_page_setting = UserSetting.query.filter_by(key='per_page_summary_month').first()
    if per_page_setting and per_page_setting.value and per_page_setting.value.isdigit():
        per_page_value = int(per_page_setting.value)
        if per_page_value <= 0: # Ensure positive value
            per_page_value = 12 # Fallback to a sensible default (e.g., from DEFAULT_SETTINGS in settings.py)
            current_app.logger.warning("per_page_summary_month setting is not positive, using default 12.")
    else:
        per_page_value = 12 # Default if setting not found or invalid
        if per_page_setting: # Log if found but invalid
            current_app.logger.warning(f"per_page_summary_month setting '{per_page_setting.value}' is invalid, using default 12.")
        else: # Log if not found
            current_app.logger.info("per_page_summary_month setting not found, using default 12.")

    # == Query Total Count for Pagination ============================================
    count_result = db.session.execute(text("SELECT COUNT(*) FROM mv_month_totals")).scalar()
    total_pages = (count_result + per_page_value - 1) // per_page_value if count_result > 0 else 1

    # == Page Number Validation and Redirection ============================================
    if page_num < 1:
        page_num = 1
    elif page_num > total_pages and total_pages > 0:
        return redirect(url_for('summary_month_paginated', page_num=total_pages)) # Updated url_for
    elif page_num > total_pages and total_pages == 0: 
        return redirect(url_for('summary_month_paginated', page_num=1)) # Updated url_for

    # == Calculate Offset for SQL Query ============================================
    offset = (page_num - 1) * per_page_value

    # == Query Data for Current Page ============================================
    # Data is fetched DESC for table display. A reversed copy will be used for the chart.
    summary_month_raw_results_desc = db.session.execute(text(f"""
        SELECT
            year,
            month,
            total_meters_rowed,
            total_seconds_rowed,
            average_split_seconds_per_500m AS split,
            total_isoreps_sum
        FROM
            mv_month_totals
        ORDER BY
            year DESC, month DESC
        LIMIT :limit OFFSET :offset
    """), {'limit': per_page_value, 'offset': offset}).fetchall()

    # == Prepare Data for Template ============================================
    summary_month_display_data = [] # Renamed variable
    for row in summary_month_raw_results_desc:
        summary_month_display_data.append({ # Renamed variable
            'year': int(row.year),
            'month': int(row.month),
            'month_name': datetime(int(row.year), int(row.month), 1).strftime('%B'),
            'meters': float(row.total_meters_rowed) if row.total_meters_rowed is not None else 0,
            'seconds': float(row.total_seconds_rowed) if row.total_seconds_rowed is not None else 0,
            'split': float(row.split) if row.split is not None else 0,
            'isoreps': float(row.total_isoreps_sum) if row.total_isoreps_sum is not None else 0
        })

    # == Custom Pagination Object ============================================
    summary_month_pagination = CustomPagination(page_num, per_page_value, count_result, summary_month_display_data) # Renamed variable

    # == Prepare Data for Chart ============================================
    # Use the paginated data (reversed for chronological order) for the chart.
    chart_data_source = list(reversed(summary_month_raw_results_desc))

    chart_categories_months = []
    chart_series_data_meters = []
    chart_series_data_seconds = []
    chart_series_data_pace = []
    chart_series_data_reps = []

    if chart_data_source: # Process the paginated (and reversed) data
        for row in chart_data_source:
            month_year_str = datetime(int(row.year), int(row.month), 1).strftime('%B %Y')
            chart_categories_months.append(month_year_str)
            
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
        'summary_month.html', # Updated template name
        summary_month_pagination=summary_month_pagination, # Renamed variable
        summary_month_display_data=summary_month_display_data, # Renamed variable
        page_title="Monthly Workout Summaries",
        # Chart data
        chart_categories_months=chart_categories_months,
        series_data_meters=chart_series_data_meters, # Re-using standard names for template consistency
        series_data_seconds=chart_series_data_seconds,
        series_data_pace=chart_series_data_pace,
        series_data_reps=chart_series_data_reps,
        has_chart_data=has_chart_data
    )

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the monthly summary view routes with the Flask application.
def register_routes(app):
    app.add_url_rule('/summary_month/', endpoint='summary_month', view_func=lambda: summary_month(1), methods=['GET']) # Updated endpoint and view_func
    app.add_url_rule('/summary_month/page/<int:page_num>', endpoint='summary_month_paginated', view_func=summary_month, methods=['GET']) # Updated endpoint and view_func