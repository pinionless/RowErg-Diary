# views/dailysummary.py
from flask import render_template, redirect, url_for, current_app
from sqlalchemy import text # Import text for raw SQL execution
from models import db # Assuming db is initialized and available

def dailysummary(page_num=1):
    per_page_value = current_app.config.get('PER_PAGE', 10) # Get PER_PAGE from app config

    # Query the materialized view directly
    # Note: Paginate from a raw SQL query can be tricky with SQLAlchemy's ORM paginate.
    # We'll use a subquery approach with ORDER BY and LIMIT/OFFSET for pagination.
    
    # First, get the total count for pagination
    count_result = db.session.execute(text("SELECT COUNT(*) FROM mv_day_totals")).scalar()
    total_pages = (count_result + per_page_value - 1) // per_page_value if count_result > 0 else 1

    # Adjust page_num if it's out of bounds (e.g., if page_num is too high)
    if page_num < 1:
        page_num = 1
    elif page_num > total_pages and total_pages > 0:
        return redirect(url_for('dailysummary_paginated', page_num=total_pages))
    elif page_num > total_pages and total_pages == 0:
        return redirect(url_for('dailysummary_paginated', page_num=1))

    # Calculate OFFSET
    offset = (page_num - 1) * per_page_value

    # Query data for the current page
    dailysummary_raw_results = db.session.execute(text(f"""
        SELECT
            day_date,
            total_meters_rowed,
            total_seconds_rowed,
            average_split_seconds_per_500m AS split
        FROM
            mv_day_totals
        ORDER BY
            day_date DESC
        LIMIT :limit OFFSET :offset
    """), {'limit': per_page_value, 'offset': offset}).fetchall()

    dailysummary_display_data = []
    for row in dailysummary_raw_results:
        dailysummary_display_data.append({
            'day_date': row.day_date,
            'meters': float(row.total_meters_rowed),
            'seconds': float(row.total_seconds_rowed),
            'split': float(row.split)
        })

    # Manually construct a pagination-like object for the template
    # Flask-SQLAlchemy's paginate object has useful attributes, so we mimic them.
    class CustomPagination:
        def __init__(self, page, per_page, total_count, items):
            self.page = page
            self.per_page = per_page
            self.total = total_count
            self.pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
            self.has_prev = self.page > 1
            self.has_next = self.page < self.pages
            self.prev_num = self.page - 1 if self.has_prev else None
            self.next_num = self.page + 1 if self.has_next else None
            self.items = items # Not strictly used for iteration in template, but good practice

        def iter_pages(self, left_edge=2, right_edge=2, left_current=2, right_current=3):
            # This is a simplified version of Flask-SQLAlchemy's iter_pages
            # You might want to copy the full logic if you need exact matching.
            last_page = 0
            for num in range(1, self.pages + 1):
                if num <= left_edge or \
                   (num > self.page - left_current - 1 and num < self.page + right_current) or \
                   num > self.pages - right_edge:
                    if last_page + 1 != num:
                        yield None # Ellipsis
                    yield num
                    last_page = num

    dailysummary_pagination = CustomPagination(page_num, per_page_value, count_result, dailysummary_display_data)


    return render_template(
        'dailysummary.html',
        dailysummary_pagination=dailysummary_pagination,
        dailysummary_display_data=dailysummary_display_data
    )

def register_routes(app):
    app.add_url_rule('/dailysummary/', endpoint='dailysummary', view_func=lambda: dailysummary(1), methods=['GET'])
    app.add_url_rule('/dailysummary/page/<int:page_num>', endpoint='dailysummary_paginated', view_func=dailysummary, methods=['GET'])