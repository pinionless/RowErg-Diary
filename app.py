# app.py
import os
from flask import Flask
from models import db
# Import your views
from views import home, submit_json_workout, workouts, details, database_management, dailysummary, workouts_by_date, submit_manual_workout
# Import your utility functions and the context processor
from utils import sidebar_stats_processor, format_total_seconds_human_readable, format_split_short, format_duration_ms # <--- IMPORT YOUR FILTERS

__version__ = "0.12"

def create_app(config_object=None):
    app = Flask(__name__)

    # Configuration
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_default_secret_key')

    DB_USER = os.environ.get('POSTGRES_USER')
    DB_PASSWORD = os.environ.get('POSTGRES_PASSWORD')
    DB_NAME = os.environ.get('POSTGRES_DB')
    DB_HOST = os.environ.get('POSTGRES_HOST', 'db')

    app.config['PER_PAGE'] = int(os.environ.get('PER_PAGE', '10'))

    app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/{DB_NAME}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)

    app.context_processor(sidebar_stats_processor)

    # Add app version to context
    @app.context_processor
    def inject_version():
        return dict(app_version=__version__)

    # <<< --- ADD THESE LINES TO REGISTER YOUR FILTERS --- >>>
    app.jinja_env.filters['format_total_seconds_human_readable'] = format_total_seconds_human_readable
    app.jinja_env.filters['format_split_short'] = format_split_short
    app.jinja_env.filters['format_split_ms'] = format_duration_ms 
    #   ^ You can choose the name you want to use in the template.
    #     e.g., if you used {{ value | format_split_ms }} in the template, this is correct.
    #     If you used {{ value | format_duration_ms }} in the template, then use:
    #     app.jinja_env.filters['format_duration_ms'] = format_duration_ms


    # Register routes
    with app.app_context():
        home.register_routes(app)
        submit_json_workout.register_routes(app)
        workouts.register_routes(app)
        details.register_routes(app)
        database_management.register_routes(app)
        dailysummary.register_routes(app)
        workouts_by_date.register_routes(app)
        submit_manual_workout.register_routes(app)

    return app

if __name__ == '__main__':
    # Make sure to create the app instance if running directly
    app = create_app() # <--- Ensure app is created
    app.run(host='0.0.0.0', port=5000, debug=True)