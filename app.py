# ========================================================
# = app.py - Main Flask application setup
# ========================================================
import os
from flask import Flask
from models import db
# --------------------------------------------------------
# - View and Utility Imports
#---------------------------------------------------------
# Import application views
from views import home, submit_json_workout, workouts, details, database_management, dailysummary, weeklysummary, monthlysummary, yearlysummary, workouts_by_date, submit_manual_workout, workouts_by_week, workouts_by_month, workouts_by_year # Added workouts_by_year
# Import utility functions and context processors
from utils import sidebar_stats_processor, format_total_seconds_human_readable, format_split_short, format_duration_ms

# --------------------------------------------------------
# - Application Version
#---------------------------------------------------------
__version__ = "0.14"

# --------------------------------------------------------
# - Application Factory Function
#---------------------------------------------------------
def create_app(config_object=None):
    # == Flask App Initialization ============================================
    app = Flask(__name__)

    # == Configuration Settings ============================================
    # -- General Flask Configuration -------------------
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # Max content length for uploads
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'your_default_secret_key') # Secret key for session management
    app.config['PER_PAGE'] = int(os.environ.get('PER_PAGE', '10')) # Items per page for pagination

    # -- Database Configuration -------------------
    DB_USER = os.environ.get('POSTGRES_USER') # PostgreSQL username
    DB_PASSWORD = os.environ.get('POSTGRES_PASSWORD') # PostgreSQL password
    DB_NAME = os.environ.get('POSTGRES_DB') # PostgreSQL database name
    DB_HOST = os.environ.get('POSTGRES_HOST', 'db') # PostgreSQL host

    app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/{DB_NAME}' # SQLAlchemy database URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Disable SQLAlchemy event system
    
    # == Database Initialization ============================================
    db.init_app(app) # Initialize SQLAlchemy with the Flask app

    # == Context Processors ============================================
    app.context_processor(sidebar_stats_processor) # Register sidebar stats processor

    # == Inject App Version into Templates ============================================
    @app.context_processor
    def inject_version():
        # Makes app_version available in all templates
        return dict(app_version=__version__)

    # == Jinja Filters ============================================
    # Register custom Jinja2 filters for template formatting
    app.jinja_env.filters['format_total_seconds_human_readable'] = format_total_seconds_human_readable
    app.jinja_env.filters['format_split_short'] = format_split_short
    app.jinja_env.filters['format_split_ms'] = format_duration_ms 
    
    # == Route Registration ============================================
    # Register blueprints and routes from view modules
    with app.app_context():
        home.register_routes(app) # Registers routes for home page
        submit_json_workout.register_routes(app) # Registers routes for submitting JSON workouts
        workouts.register_routes(app) # Registers routes for displaying workouts list
        details.register_routes(app) # Registers routes for workout details page
        database_management.register_routes(app) # Registers routes for database management tasks
        dailysummary.register_routes(app) # Registers routes for daily summary page
        weeklysummary.register_routes(app) # Registers routes for weekly summary page
        monthlysummary.register_routes(app) # Registers routes for monthly summary page
        yearlysummary.register_routes(app) # Registers routes for yearly summary page
        workouts_by_date.register_routes(app) # Registers routes for viewing workouts by specific date
        workouts_by_week.register_routes(app) # Registers routes for viewing workouts by specific week
        workouts_by_month.register_routes(app) # Registers routes for viewing workouts by specific month
        workouts_by_year.register_routes(app) # Registers routes for viewing workouts by specific year
        submit_manual_workout.register_routes(app) # Registers routes for submitting manual workouts

    return app

# --------------------------------------------------------
# - Main Execution Block
#---------------------------------------------------------
if __name__ == '__main__':
    # Ensure the Flask app instance is created when running directly
    app = create_app() 
    # Run the Flask development server
    app.run(host='0.0.0.0', port=5000, debug=True)