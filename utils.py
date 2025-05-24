# utils.py
from flask import current_app # <--- ADD THIS LINE
from models import db
from sqlalchemy import text
from datetime import datetime, timedelta

def format_duration_ms(total_seconds):
    if total_seconds is None or not isinstance(total_seconds, (int, float)) or total_seconds < 0:
        return "00:00.00"
    total_seconds_float = float(total_seconds)
    minutes = int(total_seconds_float // 60)
    remaining_seconds_component = total_seconds_float % 60
    seconds = int(remaining_seconds_component)
    centiseconds = int((remaining_seconds_component - seconds) * 100)
    return f"{minutes:02d}:{seconds:02d}.{centiseconds:02d}"

def sidebar_stats_processor():
    """
    Fetches various rowing statistics from materialized views for the sidebar.
    """
    stats = {}
    try:
        with db.engine.connect() as connection:
            # 1. Overall Totals
            overall_totals_result = connection.execute(text("SELECT * FROM mv_sum_totals LIMIT 1")).fetchone()
            stats['overall_totals'] = {
                'meters': float(overall_totals_result.total_meters_rowed) if overall_totals_result else 0,
                'seconds': float(overall_totals_result.total_seconds_rowed) if overall_totals_result else 0,
                'split': float(overall_totals_result.average_split_seconds_per_500m) if overall_totals_result else 0
            }

    except Exception as e:
        current_app.logger.error(f"Error fetching sidebar stats: {e}", exc_info=True)
        # Provide empty/default values on error to prevent template errors
        stats = {
            'overall_totals': {'meters': 0, 'seconds': 0, 'split': 0},
        }
    
    return dict(sidebar_stats=stats) # This makes `sidebar_stats` available in templates