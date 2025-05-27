# ========================================================
# = dailysummary.py - View for displaying paginated daily workout summaries
# ========================================================
from flask import render_template, redirect, url_for, current_app
from sqlalchemy import text # Import text for raw SQL execution
from models import db # Assuming db is initialized and available
from utils import CustomPagination # Import CustomPagination from utils

# --------------------------------------------------------
# - Daily Summary View Function
#---------------------------------------------------------
# Displays paginated daily workout summaries from the mv_day_totals materialized view.
def dailysummary(page_num=1):
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
        return redirect(url_for('dailysummary_paginated', page_num=total_pages))
    elif page_num > total_pages and total_pages == 0: # If no data, redirect to page 1
        return redirect(url_for('dailysummary_paginated', page_num=1))

    # == Calculate Offset for SQL Query ============================================
    offset = (page_num - 1) * per_page_value # Calculate the starting point for records on the current page

    # == Query Data for Current Page ============================================
    # Fetch daily summary data for the current page using LIMIT and OFFSET.
    dailysummary_raw_results = db.session.execute(text(f"""
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
    for row in dailysummary_raw_results:
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

    # == Render Template ============================================
    return render_template(
        'dailysummary.html',
        dailysummary_pagination=dailysummary_pagination, # Pass pagination object to template
        dailysummary_display_data=dailysummary_display_data # Pass display data to template
    )

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the daily summary view routes with the Flask application.
def register_routes(app):
    app.add_url_rule('/dailysummary/', endpoint='dailysummary', view_func=lambda: dailysummary(1), methods=['GET']) # Route for the first page
    app.add_url_rule('/dailysummary/page/<int:page_num>', endpoint='dailysummary_paginated', view_func=dailysummary, methods=['GET']) # Route for subsequent pages