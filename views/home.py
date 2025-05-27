# ========================================================
# = home.py - View for the home page
# ========================================================
from flask import render_template
from models import Workout

# --------------------------------------------------------
# - Home View Function
#---------------------------------------------------------
# Displays the home page with the latest five workouts.
def home():
    # == Query Latest Workouts ============================================
    # Fetch the latest five workouts, ordered by date and then ID for consistency
    latest_five_workouts = Workout.query.order_by(
        Workout.workout_date.desc(), # Order by workout date descending
        Workout.workout_id.desc() # Then by workout ID descending
    ).limit(5).all() # Limit to 5 results

    # == Prepare Data for Template ============================================
    # The template (index.html) will directly use workout objects and Jinja filters for formatting.
    # Data is wrapped to maintain consistency with how templates might expect 'item_data.workout_obj'.
    workouts_display_data = []
    for workout_item in latest_five_workouts: # Iterate through the fetched workouts
        workouts_display_data.append({
            'workout_obj': workout_item, # Pass the raw workout object
            'name': workout_item.workout_name # Include workout name for direct access in template
        })

    # == Render Template ============================================
    return render_template('index.html',
        workouts_display_data=workouts_display_data # Pass the prepared list of workouts
    )

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the home page route with the Flask application
def register_routes(app):
    app.add_url_rule('/', view_func=home, methods=['GET']) # Root URL for the application