# ========================================================
# = ranking.py - View for displaying rankings
# ========================================================
from flask import Blueprint, render_template, current_app
from models import db, Workout, RankingSetting
from sqlalchemy import text, func
from utils import format_split_short, format_duration_ms, format_seconds_to_hms

ranking_bp = Blueprint('ranking', __name__, url_prefix='/ranking')

def get_rankings_from_mv(ranking_id, year=None, limit=10, rank_type='overall'):
    """
    Fetches workout rankings from the materialized view.
    
    Args:
        ranking_id: The ID of the ranking setting
        year: Optional year to filter by 
        limit: Maximum number of results to return
        rank_type: Type of ranking ('overall', 'year', 'month')
    
    Returns:
        List of workout ranking data
    """
    try:
        # Start with a base query for the specified ranking ID and rank type
        query = text("""
            SELECT 
                r.id, 
                r.ranking_id, 
                r.workout_id, 
                r.rank,
                w.workout_date,
                w.total_distance_meters,
                w.duration_seconds,
                w.average_split_seconds_500m,
                rs.type,
                rs.value as setting_value
            FROM 
                mv_workout_rankings r
                JOIN workouts w ON w.workout_id = r.workout_id
                JOIN ranking_settings rs ON rs.ranking_id = r.ranking_id
            WHERE 
                r.ranking_id = :ranking_id
                AND r.rank_type = :rank_type
        """)
        
        params = {'ranking_id': ranking_id, 'rank_type': rank_type, 'limit': limit}
        
        # Add year filter if specified
        if year is not None and rank_type != 'overall':
            query = text(query.text + " AND r.year = :year")
            params['year'] = year
        
        # Add ordering and limit
        query = text(query.text + " ORDER BY r.rank LIMIT :limit")
        
        # Execute the query
        result = db.session.execute(query, params).fetchall()
        return result
    
    except Exception as e:
        current_app.logger.error(f"Error fetching rankings for ID {ranking_id}: {e}", exc_info=True)
        return []

def get_available_years():
    """Get years that have ranking data available"""
    try:
        # Query distinct years from the materialized view
        query = text("""
            SELECT DISTINCT year 
            FROM mv_workout_rankings 
            WHERE year IS NOT NULL 
            ORDER BY year DESC
        """)
        result = db.session.execute(query).fetchall()
        return [row[0] for row in result]
    except Exception as e:
        current_app.logger.error(f"Error fetching available years: {e}", exc_info=True)
        return []

@ranking_bp.route('/', defaults={'year_param': None})
@ranking_bp.route('/<int:year_param>')
def index(year_param):
    selected_year = year_param
    page_title = "Athlete Rankings"
    if selected_year:
        page_title = f"Athlete Rankings {selected_year}"
    
    # Get all ranking settings from database without sorting (use natural database order)
    try:
        # Remove the order_by to preserve the insertion order
        ranking_settings = db.session.query(RankingSetting).all()
    except Exception as e:
        current_app.logger.error(f"Error fetching ranking settings: {e}", exc_info=True)
        ranking_settings = []
    
    # Get available years
    available_years = get_available_years()
    
    # Fetch rankings for each setting
    all_rankings_data = []
    rank_type = 'year' if selected_year else 'overall'

    for setting in ranking_settings:
        rankings = get_rankings_from_mv(
            setting.ranking_id, 
            year=selected_year, 
            limit=10,
            rank_type=rank_type
        )
        
        all_rankings_data.append({
            'type': setting.type,
            'label': setting.label,
            'rankings': rankings
        })

    return render_template(
        'ranking.html',
        page_title=page_title,
        all_rankings_data=all_rankings_data,
        available_years=available_years,
        selected_year=selected_year
    )

def register_routes(app):
    app.register_blueprint(ranking_bp)
