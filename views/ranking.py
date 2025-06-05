# ========================================================
# = ranking.py - View for displaying rankings
# ========================================================
from flask import Blueprint, render_template, flash, current_app
from models import db, Workout, EquipmentType
from utils import format_split_short, format_duration_ms, format_seconds_to_hms # Ensure utils are imported
from sqlalchemy import extract # For extracting year

ranking_bp = Blueprint('ranking', __name__, url_prefix='/ranking')

def get_rankings_for_distance(distance_meters, year=None, limit=10):
    """
    Fetches workout rankings for a specific distance, optionally filtered by year.
    - Filters by exact distance.
    - Considers only equipment types marked 'settings_include_in_totals = TRUE'.
    - Orders by average_split_seconds_500m (lower is better).
    - Limits results.
    - Optionally filters by year.
    """
    try:
        query = db.session.query(
                Workout.average_split_seconds_500m,
                Workout.duration_seconds,
                Workout.workout_date,
                Workout.workout_id
            ).\
            join(EquipmentType, Workout.equipment_type_id == EquipmentType.equipment_type_id).\
            filter(Workout.total_distance_meters == distance_meters).\
            filter(EquipmentType.settings_include_in_totals == True).\
            filter(Workout.average_split_seconds_500m != None).\
            filter(Workout.average_split_seconds_500m > 0)

        if year:
            query = query.filter(extract('year', Workout.workout_date) == year)
        
        rankings = query.order_by(Workout.average_split_seconds_500m.asc()).\
            limit(limit).\
            all()
        return rankings
    except Exception as e:
        current_app.logger.error(f"Error fetching distance rankings for {distance_meters}m (year: {year}): {e}", exc_info=True)
        return []

def get_rankings_for_duration(duration_seconds, year=None, limit=10):
    """
    Fetches workout rankings for a specific duration, optionally filtered by year.
    - Filters by exact duration.
    - Considers only equipment types marked 'settings_include_in_totals = TRUE'.
    - Orders by total_distance_meters (higher is better).
    - Limits results.
    - Optionally filters by year.
    """
    try:
        query = db.session.query(
                Workout.total_distance_meters,
                Workout.average_split_seconds_500m,
                Workout.workout_date,
                Workout.workout_id,
                Workout.duration_seconds
            ).\
            join(EquipmentType, Workout.equipment_type_id == EquipmentType.equipment_type_id).\
            filter(Workout.duration_seconds == duration_seconds).\
            filter(EquipmentType.settings_include_in_totals == True).\
            filter(Workout.total_distance_meters != None).\
            filter(Workout.total_distance_meters > 0)

        if year:
            query = query.filter(extract('year', Workout.workout_date) == year)

        rankings = query.order_by(Workout.total_distance_meters.desc()).\
            limit(limit).\
            all()
        return rankings
    except Exception as e:
        current_app.logger.error(f"Error fetching duration rankings for {duration_seconds}s (year: {year}): {e}", exc_info=True)
        return []


@ranking_bp.route('/', defaults={'year_param': None})
@ranking_bp.route('/<int:year_param>')
def index(year_param):
    selected_year = year_param
    page_title = "Athlete Rankings"
    if selected_year:
        page_title = f"Athlete Rankings {selected_year}"
    
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

    # Fetch candidate years first
    candidate_years_query = db.session.query(extract('year', Workout.workout_date).label('year')).distinct().order_by(extract('year', Workout.workout_date).desc()).all()
    candidate_years = [y.year for y in candidate_years_query if y.year is not None]

    available_years = []
    for year_val in candidate_years:
        year_has_rankable_data = False
        for config in ranking_configurations:
            rankings_check = []
            if config['type'] == 'distance':
                # Check if any rankable workout exists for this config and year
                rankings_check = get_rankings_for_distance(config['value'], year=year_val, limit=1)
            elif config['type'] == 'time':
                # Check if any rankable workout exists for this config and year
                rankings_check = get_rankings_for_duration(config['value'], year=year_val, limit=1)
            
            if rankings_check: # If the list is not empty, means at least one rankable item found
                year_has_rankable_data = True
                break # No need to check other configs for this year
        
        if year_has_rankable_data:
            available_years.append(year_val)
    # available_years will be sorted based on the initial query order (descending)
    
    all_rankings_data = []

    for config in ranking_configurations:
        rankings = []
        if config['type'] == 'distance':
            rankings = get_rankings_for_distance(config['value'], year=selected_year)
        elif config['type'] == 'time':
            rankings = get_rankings_for_duration(config['value'], year=selected_year)
        
        all_rankings_data.append({
            'type': config['type'],
            'label': config['label'],
            'rankings': rankings
        })

    return render_template(
        'ranking.html',
        page_title=page_title,
        all_rankings_data=all_rankings_data,
        available_years=available_years, # Use the filtered list
        selected_year=selected_year
    )

def register_routes(app):
    app.register_blueprint(ranking_bp)
