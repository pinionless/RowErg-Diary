# ========================================================
# = monthlysummary.py - View for displaying paginated monthly workout summaries
# ========================================================
from flask import render_template, redirect, url_for, current_app
from sqlalchemy import text
from models import db 
from utils import CustomPagination 
from datetime import datetime

# --------------------------------------------------------
# - Monthly Summary View Function
#---------------------------------------------------------
# Displays paginated monthly workout summaries from the mv_month_totals materialized view.
def monthlysummary(page_num=1):
    # == Pagination Configuration ============================================
    per_page_value = current_app.config.get('PER_PAGE', 10) 

    # == Query Total Count for Pagination ============================================
    count_result = db.session.execute(text("SELECT COUNT(*) FROM mv_month_totals")).scalar()
    total_pages = (count_result + per_page_value - 1) // per_page_value if count_result > 0 else 1

    # == Page Number Validation and Redirection ============================================
    if page_num < 1:
        page_num = 1
    elif page_num > total_pages and total_pages > 0:
        return redirect(url_for('monthlysummary_paginated', page_num=total_pages))
    elif page_num > total_pages and total_pages == 0: 
        return redirect(url_for('monthlysummary_paginated', page_num=1))

    # == Calculate Offset for SQL Query ============================================
    offset = (page_num - 1) * per_page_value

    # == Query Data for Current Page ============================================
    monthlysummary_raw_results = db.session.execute(text(f"""
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
    monthlysummary_display_data = []
    for row in monthlysummary_raw_results:
        monthlysummary_display_data.append({
            'year': int(row.year),
            'month': int(row.month),
            'month_name': datetime(int(row.year), int(row.month), 1).strftime('%B'),
            'meters': float(row.total_meters_rowed) if row.total_meters_rowed is not None else 0,
            'seconds': float(row.total_seconds_rowed) if row.total_seconds_rowed is not None else 0,
            'split': float(row.split) if row.split is not None else 0,
            'isoreps': float(row.total_isoreps_sum) if row.total_isoreps_sum is not None else 0
        })

    # == Custom Pagination Object ============================================
    monthlysummary_pagination = CustomPagination(page_num, per_page_value, count_result, monthlysummary_display_data)

    # == Render Template ============================================
    return render_template(
        'monthlysummary.html',
        monthlysummary_pagination=monthlysummary_pagination,
        monthlysummary_display_data=monthlysummary_display_data,
        page_title="Monthly Workout Summaries"
    )

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the monthly summary view routes with the Flask application.
def register_routes(app):
    app.add_url_rule('/monthlysummary/', endpoint='monthlysummary', view_func=lambda: monthlysummary(1), methods=['GET'])
    app.add_url_rule('/monthlysummary/page/<int:page_num>', endpoint='monthlysummary_paginated', view_func=monthlysummary, methods=['GET'])
