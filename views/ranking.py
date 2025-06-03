# ========================================================
# = ranking.py - View for displaying rankings
# ========================================================
from flask import Blueprint, render_template, flash, current_app
from models import db, Workout, EquipmentType
from utils import format_split_short, format_duration_ms, format_seconds_to_hms # Ensure utils are imported

ranking_bp = Blueprint('ranking', __name__, url_prefix='/ranking')

def get_rankings_for_distance(distance_meters, limit=10):
    """
    Fetches workout rankings for a specific distance.
    - Filters by exact distance.
    - Considers only equipment types marked 'settings_include_in_totals = TRUE'.
    - Orders by average_split_seconds_500m (lower is better).
    - Limits results.
    """
    try:
        rankings = db.session.query(
                Workout.average_split_seconds_500m,
                Workout.duration_seconds,
                Workout.workout_date,
                Workout.workout_id
            ).\
            join(EquipmentType, Workout.equipment_type_id == EquipmentType.equipment_type_id).\
            filter(Workout.total_distance_meters == distance_meters).\
            filter(EquipmentType.settings_include_in_totals == True).\
            filter(Workout.average_split_seconds_500m != None).\
            filter(Workout.average_split_seconds_500m > 0).\
            order_by(Workout.average_split_seconds_500m.asc()).\
            limit(limit).\
            all()
        return rankings
    except Exception as e:
        current_app.logger.error(f"Error fetching distance rankings for {distance_meters}m: {e}", exc_info=True)
        return []

def get_rankings_for_duration(duration_seconds, limit=10):
    """
    Fetches workout rankings for a specific duration.
    - Filters by exact duration.
    - Considers only equipment types marked 'settings_include_in_totals = TRUE'.
    - Orders by total_distance_meters (higher is better).
    - Limits results.
    """
    try:
        rankings = db.session.query(
                Workout.total_distance_meters,
                Workout.average_split_seconds_500m,
                Workout.workout_date,
                Workout.workout_id,
                Workout.duration_seconds # Keep for consistency if needed, though primary sort is distance
            ).\
            join(EquipmentType, Workout.equipment_type_id == EquipmentType.equipment_type_id).\
            filter(Workout.duration_seconds == duration_seconds).\
            filter(EquipmentType.settings_include_in_totals == True).\
            filter(Workout.total_distance_meters != None).\
            filter(Workout.total_distance_meters > 0).\
            order_by(Workout.total_distance_meters.desc()).\
            limit(limit).\
            all()
        return rankings
    except Exception as e:
        current_app.logger.error(f"Error fetching duration rankings for {duration_seconds}s: {e}", exc_info=True)
        return []


@ranking_bp.route('/')
def index():
    page_title = "Athlete Rankings"
    
    # Define ranking configurations: type, value (meters or seconds), label for display
    ranking_configurations = [
        {'type': 'distance', 'value': 2000, 'label': '2000m'},
        {'type': 'distance', 'value': 5000, 'label': '5000m'},
        {'type': 'distance', 'value': 100, 'label': '100m'},
        {'type': 'distance', 'value': 500, 'label': '500m'},
        {'type': 'distance', 'value': 1000, 'label': '1000m'},
        {'type': 'distance', 'value': 6000, 'label': '6000m'},
        {'type': 'distance', 'value': 10000, 'label': '10000m'},
        {'type': 'distance', 'value': 21097, 'label': 'Half Marathon'},
        {'type': 'time', 'value': 60, 'label': '1:00'},      # 1 minute
        {'type': 'time', 'value': 240, 'label': '4:00'},     # 4 minutes
        {'type': 'time', 'value': 1800, 'label': '30:00'},   # 30 minutes
        {'type': 'time', 'value': 3600, 'label': '60:00'},   # 20 minutes
    ]
    
    all_rankings_data = []

    for config in ranking_configurations:
        rankings = []
        if config['type'] == 'distance':
            rankings = get_rankings_for_distance(config['value'])
        elif config['type'] == 'time':
            rankings = get_rankings_for_duration(config['value'])
        
        all_rankings_data.append({
            'type': config['type'],
            'label': config['label'],
            'rankings': rankings
        })

    return render_template(
        'ranking.html',
        page_title=page_title,
        all_rankings_data=all_rankings_data
    )

def register_routes(app):
    app.register_blueprint(ranking_bp)
