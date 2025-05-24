# app.py
import os
from flask import Flask
from models import db
from views import home, submit_json_workout, workouts, details, database_management, dailysummary
from utils import sidebar_stats_processor

__version__ = "0.1beta"

def create_app(config_object=None):
    app = Flask(__name__)

    # Configuration
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_default_secret_key')

    DB_USER = os.environ.get('POSTGRES_USER')
    DB_PASSWORD = os.environ.get('POSTGRES_PASSWORD')
    DB_NAME = os.environ.get('POSTGRES_DB')
    DB_HOST = os.environ.get('POSTGRES_HOST', 'db')

    app.config['PER_PAGE'] = int(os.environ.get('PER_PAGE', '10')) # Default to 10 if not found/invalid

    app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/{DB_NAME}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    


    db.init_app(app)

    app.context_processor(sidebar_stats_processor) # <--- ADD THIS LINE

    # Register routes
    with app.app_context():
        home.register_routes(app)
        submit_json_workout.register_routes(app)
        workouts.register_routes(app)
        details.register_routes(app)
        database_management.register_routes(app)
        dailysummary.register_routes(app)

    return app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)