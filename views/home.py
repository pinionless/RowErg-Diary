# ========================================================
# = home.py - View for the home page
# ========================================================
from flask import render_template, current_app
from models import db, Workout, MetricDescriptor, WorkoutSample, EquipmentType # Ensure all are imported
from sqlalchemy import desc
import json

# --------------------------------------------------------
# - Home View Function
#---------------------------------------------------------
# Displays the home page with the latest five workouts.
def home():
    # == Query Equipment Types for dropdown =================================
    equipment_types = EquipmentType.query.order_by(EquipmentType.name).all()

    # == Render Template ============================================
    return render_template('index.html', equipment_types=equipment_types)

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the home page route with the Flask application
def register_routes(app):
    app.add_url_rule('/', view_func=home, methods=['GET']) # Root URL for the application