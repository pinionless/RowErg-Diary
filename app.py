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
from views import home, submit_json_workout, workouts, details, summary_day, summary_week, summary_month, summary_year, workouts_by_date, submit_manual_workout, workouts_by_week, workouts_by_month, workouts_by_year, settings, ranking
# Import utility functions and context processors
from utils import nl2br_filter, sidebar_stats_processor, utility_processor, format_seconds_to_hms, format_split_short, format_duration_ms, format_total_seconds_human_readable # Added utility_processor
from database_setup import create_db_components, update_db_schema # Import database setup functions
from sqlalchemy.exc import ProgrammingError # To catch errors like "table not found"

# --------------------------------------------------------
# - Application Version
#---------------------------------------------------------
__version__ = "0.16.0" # Current application version
TARGET_DB_SCHEMA_VERSION = "0.16" # Target schema version for this change

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
    app.config['TARGET_DB_SCHEMA_VERSION'] = TARGET_DB_SCHEMA_VERSION # Store in app config

    # -- Database Configuration -------------------
    DB_USER = os.environ.get('POSTGRES_USER') # PostgreSQL username
    DB_PASSWORD = os.environ.get('POSTGRES_PASSWORD') # PostgreSQL password
    DB_NAME = os.environ.get('POSTGRES_DB') # PostgreSQL database name
    DB_HOST = os.environ.get('POSTGRES_HOST', 'db') # PostgreSQL host

    app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/{DB_NAME}' # SQLAlchemy database URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Disable SQLAlchemy event system
    
    # == Database Initialization ============================================
    db.init_app(app) # Initialize SQLAlchemy with the Flask app

    # == Database Schema Check and Initialization/Update =====================
    with app.app_context():
        from models import UserSetting # Import UserSetting model here to avoid circular dependency at module level

        try:
            # Attempt to get the current DB schema version
            db_schema_ver_setting = db.session.query(UserSetting).filter_by(key='db_schema_ver').first()
            
            if db_schema_ver_setting is None:
                # Key 'db_schema_ver' not found in an existing user_settings table,
                # or table might be empty. Run full setup.
                app.logger.info("'db_schema_ver' key not found. Running initial database setup.")
                create_db_components() # This will create tables if needed and set the schema version.
            else:
                current_db_schema_ver = db_schema_ver_setting.value
                target_schema_ver_from_config = app.config['TARGET_DB_SCHEMA_VERSION']
                if current_db_schema_ver != target_schema_ver_from_config:
                    app.logger.info(f"DB schema version mismatch. Current: {current_db_schema_ver}, Target: {target_schema_ver_from_config}. Running update.")
                    update_db_schema(current_db_schema_ver, target_schema_ver_from_config)
                else:
                    app.logger.info(f"DB schema version {current_db_schema_ver} is up to date.")

        except ProgrammingError as e:
            # This typically means the 'user_settings' table (or others) doesn't exist.
            # Common error messages: "relation \"user_settings\" does not exist" (PostgreSQL)
            # or "no such table: user_settings" (SQLite)
            db.session.rollback() # Rollback any transaction from the failed query
            app.logger.warning(f"ProgrammingError during DB schema check (likely tables missing): {e}. Running initial database setup.")
            create_db_components() # Create all tables and set initial schema version.
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"An unexpected error occurred during DB schema check: {e}", exc_info=True)
            # Depending on the severity, you might want to prevent the app from starting.
            # For now, we'll log and continue, but this could be critical.
            # raise # Uncomment to make this a fatal error

    # == Register Jinja Filters and Context Processors ============================================
        app.jinja_env.filters['nl2br'] = nl2br_filter
        app.jinja_env.filters['format_seconds_to_hms'] = format_seconds_to_hms
        app.jinja_env.filters['format_split_short'] = format_split_short
        app.jinja_env.filters['format_duration_ms'] = format_duration_ms
        app.jinja_env.filters['format_total_seconds_human_readable'] = format_total_seconds_human_readable
        
        app.context_processor(sidebar_stats_processor) # For sidebar statistics
        app.context_processor(utility_processor) # For utility functions like now()

        # == Register Blueprints for different application modules ============================================
        # Each blueprint corresponds to a feature or section of the application
        home.register_routes(app) # Registers routes for home page
        submit_json_workout.register_routes(app) # Registers routes for submitting JSON workouts
        workouts.register_routes(app) # Registers routes for displaying workouts list
        details.register_routes(app) # Registers routes for workout details page
        summary_day.register_routes(app) # Registers routes for daily summary page
        summary_week.register_routes(app) # Registers routes for weekly summary page
        summary_month.register_routes(app) # Registers routes for monthly summary page
        summary_year.register_routes(app) # Registers routes for yearly summary page
        workouts_by_date.register_routes(app) # Registers routes for viewing workouts by specific date
        workouts_by_week.register_routes(app) # Registers routes for viewing workouts by specific week
        workouts_by_month.register_routes(app) # Registers routes for viewing workouts by specific month
        workouts_by_year.register_routes(app) # Registers routes for viewing workouts by specific year
        submit_manual_workout.register_routes(app) # Registers routes for submitting manual workouts
        settings.register_routes(app)       # Registers routes for settings page
        ranking.register_routes(app)        # Registers routes for ranking page

    return app

# --------------------------------------------------------
# - Main Execution Block
#---------------------------------------------------------
if __name__ == '__main__':
    # Ensure the Flask app instance is created when running directly
    app = create_app() 
    # Run the Flask development server
    app.run(host='0.0.0.0', port=5000, debug=True)