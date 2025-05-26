from flask import current_app
from models import db
from sqlalchemy import text
from decimal import Decimal

def parse_duration_to_seconds(time_str):
    if not time_str:
        return None
    
    parts = time_str.split(':')
    total_seconds = 0
    
    try:
        if len(parts) == 3:
            h = int(parts[0])
            m = int(parts[1])
            s_ms_part = float(parts[2])
            total_seconds = h * 3600 + m * 60 + s_ms_part
        elif len(parts) == 2:
            m = int(parts[0])
            s_ms_part = float(parts[1])
            total_seconds = m * 60 + s_ms_part
        elif len(parts) == 1:
            s_ms_part = float(parts[0])
            total_seconds = s_ms_part
        else:
            return None
        return total_seconds
    except ValueError:
        return None
        
def format_duration_ms(total_seconds):
    if total_seconds is None or not isinstance(total_seconds, (int, float, Decimal)) or total_seconds < 0:
        return "00:00.00"
    total_seconds_float = float(total_seconds)
    minutes = int(total_seconds_float // 60)
    remaining_seconds_component = total_seconds_float % 60
    seconds = int(remaining_seconds_component)
    centiseconds = int((remaining_seconds_component - seconds) * 100)
    return f"{minutes:02d}:{seconds:02d}.{centiseconds:02d}"

def sidebar_stats_processor():
    stats = {}
    try:
        with db.engine.connect() as connection:
            overall_totals_result = connection.execute(text("SELECT * FROM mv_sum_totals LIMIT 1")).fetchone()
            if overall_totals_result:
                stats['overall_totals'] = {
                    'meters': float(overall_totals_result.total_meters_rowed) if overall_totals_result.total_meters_rowed is not None else 0,
                    'seconds': float(overall_totals_result.total_seconds_rowed) if overall_totals_result.total_seconds_rowed is not None else 0,
                    'split': float(overall_totals_result.average_split_seconds_per_500m) if overall_totals_result.average_split_seconds_per_500m is not None else 0
                }
            else:
                stats['overall_totals'] = {'meters': 0, 'seconds': 0, 'split': 0}


    except Exception as e:
        current_app.logger.error(f"Error fetching sidebar stats: {e}", exc_info=True)
        stats = {
            'overall_totals': {'meters': 0, 'seconds': 0, 'split': 0},
        }
    
    return dict(sidebar_stats=stats)


def format_total_seconds_human_readable(total_seconds):
    if total_seconds is None or not isinstance(total_seconds, (int, float, Decimal)) or total_seconds < 0:
        return "N/A"
    
    total_seconds = float(total_seconds)

    days = int(total_seconds // (24 * 3600))
    remaining_seconds_after_days = total_seconds % (24 * 3600)
    hours = int(remaining_seconds_after_days // 3600)
    remaining_seconds_after_hours = remaining_seconds_after_days % 3600
    minutes = int(remaining_seconds_after_hours // 60)
    seconds = int(remaining_seconds_after_hours % 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0: 
        parts.append(f"{hours:02d}h" if days > 0 else f"{hours}h")
    elif days > 0:
         parts.append("00h")
    
    if total_seconds >= 0:
         parts.append(f"{minutes:02d}m")
         parts.append(f"{seconds:02d}s")
    
    if not parts:
        return "00m:00s"
        
    return ":".join(parts)

def format_split_short(total_split_seconds_raw):
    if total_split_seconds_raw is None or not isinstance(total_split_seconds_raw, (int, float, Decimal)) or total_split_seconds_raw <= 0:
        return "N/A"
    
    total_split_seconds_raw = float(total_split_seconds_raw)
    minutes = int(total_split_seconds_raw // 60)
    remaining_seconds_float = total_split_seconds_raw % 60
    
    seconds_and_ms_combined_truncated = int(remaining_seconds_float * 10) 
    
    seconds_part = int(seconds_and_ms_combined_truncated // 10) 
    milliseconds_decimal_part = int(seconds_and_ms_combined_truncated % 10)

    return f"{minutes}:{seconds_part:02d}.{milliseconds_decimal_part}"