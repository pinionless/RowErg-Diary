# ========================================================
# = yearlysummary.py - View for displaying paginated yearly workout summaries
# ========================================================
from flask import render_template, redirect, url_for, current_app
from sqlalchemy import text
from models import db 
from utils import CustomPagination 

# --------------------------------------------------------
# - Yearly Summary View Function
#---------------------------------------------------------
# Displays paginated yearly workout summaries from the mv_year_totals materialized view.
def yearlysummary(page_num=1):
    # == Pagination Configuration ============================================
    per_page_value = current_app.config.get('PER_PAGE', 10) 

    # == Query Total Count for Pagination ============================================
    count_result = db.session.execute(text("SELECT COUNT(*) FROM mv_year_totals")).scalar()
    total_pages = (count_result + per_page_value - 1) // per_page_value if count_result > 0 else 1

    # == Page Number Validation and Redirection ============================================
    if page_num < 1:
        page_num = 1
    elif page_num > total_pages and total_pages > 0:
        return redirect(url_for('yearlysummary_paginated', page_num=total_pages))
    elif page_num > total_pages and total_pages == 0: 
        return redirect(url_for('yearlysummary_paginated', page_num=1))

    # == Calculate Offset for SQL Query ============================================
    offset = (page_num - 1) * per_page_value

    # == Query Data for Current Page ============================================
    yearlysummary_raw_results = db.session.execute(text(f"""
        SELECT
            year,
            total_meters_rowed,
            total_seconds_rowed,
            average_split_seconds_per_500m AS split,
            total_isoreps_sum
        FROM
            mv_year_totals
        ORDER BY
            year DESC
        LIMIT :limit OFFSET :offset
    """), {'limit': per_page_value, 'offset': offset}).fetchall()

    # == Prepare Data for Template ============================================
    yearlysummary_display_data = []
    for row in yearlysummary_raw_results:
        yearlysummary_display_data.append({
            'year': int(row.year),
            'meters': float(row.total_meters_rowed) if row.total_meters_rowed is not None else 0,
            'seconds': float(row.total_seconds_rowed) if row.total_seconds_rowed is not None else 0,
            'split': float(row.split) if row.split is not None else 0,
            'isoreps': float(row.total_isoreps_sum) if row.total_isoreps_sum is not None else 0
        })

    # == Custom Pagination Object ============================================
    yearlysummary_pagination = CustomPagination(page_num, per_page_value, count_result, yearlysummary_display_data)

    # == Render Template ============================================
    return render_template(
        'yearlysummary.html',
        yearlysummary_pagination=yearlysummary_pagination,
        yearlysummary_display_data=yearlysummary_display_data,
        page_title="Yearly Workout Summaries"
    )

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the yearly summary view routes with the Flask application.
def register_routes(app):
    app.add_url_rule('/yearlysummary/', endpoint='yearlysummary', view_func=lambda: yearlysummary(1), methods=['GET'])
    app.add_url_rule('/yearlysummary/page/<int:page_num>', endpoint='yearlysummary_paginated', view_func=yearlysummary, methods=['GET'])
