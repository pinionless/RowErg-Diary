# ========================================================
# = weeklysummary.py - View for displaying paginated weekly workout summaries
# ========================================================
from flask import render_template, redirect, url_for, current_app
from sqlalchemy import text
from models import db # Assuming db is initialized and available
from utils import CustomPagination # Import CustomPagination

# --------------------------------------------------------
# - Weekly Summary View Function
#---------------------------------------------------------
# Displays paginated weekly workout summaries from the mv_week_totals materialized view.
def weeklysummary(page_num=1):
    # == Pagination Configuration ============================================
    per_page_value = current_app.config.get('PER_PAGE', 10) # Get items per page from app config

    # == Query Total Count for Pagination ============================================
    count_result = db.session.execute(text("SELECT COUNT(*) FROM mv_week_totals")).scalar()
    total_pages = (count_result + per_page_value - 1) // per_page_value if count_result > 0 else 1

    # == Page Number Validation and Redirection ============================================
    if page_num < 1:
        page_num = 1
    elif page_num > total_pages and total_pages > 0:
        return redirect(url_for('weeklysummary_paginated', page_num=total_pages))
    elif page_num > total_pages and total_pages == 0: # If no data, redirect to page 1
        return redirect(url_for('weeklysummary_paginated', page_num=1))


    # == Calculate Offset for SQL Query ============================================
    offset = (page_num - 1) * per_page_value

    # == Query Data for Current Page ============================================
    weeklysummary_raw_results = db.session.execute(text(f"""
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
    weeklysummary_display_data = []
    for row in weeklysummary_raw_results:
        iso_calendar = row.week_start_date.isocalendar()
        weeklysummary_display_data.append({
            'year': iso_calendar[0],
            'week_number': iso_calendar[1],
            'meters': float(row.total_meters_rowed) if row.total_meters_rowed is not None else 0,
            'seconds': float(row.total_seconds_rowed) if row.total_seconds_rowed is not None else 0,
            'split': float(row.split) if row.split is not None else 0,
            'isoreps': float(row.total_isoreps_sum) if row.total_isoreps_sum is not None else 0
        })

    # == Custom Pagination Object ============================================
    weeklysummary_pagination = CustomPagination(page_num, per_page_value, count_result, weeklysummary_display_data)

    # == Render Template ============================================
    return render_template(
        'weeklysummary.html',
        weeklysummary_pagination=weeklysummary_pagination,
        weeklysummary_display_data=weeklysummary_display_data,
        page_title="Weekly Workout Summaries"
    )

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the weekly summary view routes with the Flask application.
def register_routes(app):
    app.add_url_rule('/weeklysummary/', endpoint='weeklysummary', view_func=lambda: weeklysummary(1), methods=['GET'])
    app.add_url_rule('/weeklysummary/page/<int:page_num>', endpoint='weeklysummary_paginated', view_func=weeklysummary, methods=['GET'])
