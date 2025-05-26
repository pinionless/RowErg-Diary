# ========================================================
# = workouts.py - View for displaying paginated workouts
# ========================================================
from flask import render_template, redirect, url_for, current_app
from models import Workout

# --------------------------------------------------------
# - Workouts View Function
#---------------------------------------------------------
# Displays a paginated list of workouts
def workouts(page_num=1):
    # == Pagination Configuration ============================================
    per_page_value = current_app.config.get('PER_PAGE', 10) # Get items per page from app config

    # == Query Workouts ============================================
    # Fetch workouts, ordered by date and ID, paginated
    workouts_pagination = Workout.query.order_by(
        Workout.workout_date.desc(), # Order by workout date descending
        Workout.workout_id.desc() # Then by workout ID descending for consistent ordering
    ).paginate(page=page_num, per_page=per_page_value, error_out=False) # Paginate results

    # == Prepare Data for Template ============================================
    # The template will directly use workout objects and Jinja filters for formatting
    workouts_display_data = []
    for workout_item in workouts_pagination.items: # Iterate through paginated workout items
        workouts_display_data.append({
            'workout_obj': workout_item # Pass the raw workout object to the template
        })

    # == Handle Empty Page Redirects ============================================
    # If the current page is empty and not the first page, redirect to the last valid page or first page
    if not workouts_pagination.items and page_num > 1 and workouts_pagination.pages > 0 :
        return redirect(url_for('workouts_paginated', page_num=workouts_pagination.pages)) # Redirect to last page with items
    elif not workouts_pagination.items and page_num > 1 and workouts_pagination.pages == 0: # Should ideally not happen if page_num > 1
        return redirect(url_for('workouts_paginated', page_num=1)) # Redirect to first page if no pages exist (edge case)

    # == Render Template ============================================
    return render_template(
        'workouts.html',
        workouts_pagination=workouts_pagination, # Pass pagination object
        workouts_display_data=workouts_display_data # Pass prepared workout data
    )

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the workout view routes with the Flask application
def register_routes(app):
    app.add_url_rule('/workouts/', endpoint='workouts', view_func=lambda: workouts(1), methods=['GET']) # Route for the first page of workouts
    app.add_url_rule('/workouts/page/<int:page_num>', endpoint='workouts_paginated', view_func=workouts, methods=['GET']) # Route for subsequent paginated workout pages