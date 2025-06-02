# ========================================================
# = home.py - View for the home page
# ========================================================
from flask import render_template, current_app
from models import db, Workout, MetricDescriptor, WorkoutSample # Ensure all are imported
from sqlalchemy import desc
import json

# --------------------------------------------------------
# - Home View Function
#---------------------------------------------------------
# Displays the home page with the latest five workouts.
def home():
    # == Query Latest Workouts ============================================
    # Fetch the latest five workouts, ordered by date and then ID for consistency

    # == Render Template ============================================
    return render_template('index.html')

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the home page route with the Flask application
def register_routes(app):
    app.add_url_rule('/', view_func=home, methods=['GET']) # Root URL for the application