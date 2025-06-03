# ========================================================
# = utils.py - Utility functions and context processors
# ========================================================
from flask import current_app
from models import db
from sqlalchemy import text
from decimal import Decimal
from markupsafe import Markup # Import Markup for custom filters
import datetime # Import the datetime module

# --------------------------------------------------------
# - Parsing Functions
#---------------------------------------------------------
# Parses a time string into total seconds
def parse_duration_to_seconds(time_str):
    if not time_str: # Handle empty input
        return None
    
    parts = time_str.split(':')
    total_seconds = 0
    
    try:
        if len(parts) == 3: # Format H:M:S.ms
            h = int(parts[0])
            m = int(parts[1])
            s_ms_part = float(parts[2])
            total_seconds = h * 3600 + m * 60 + s_ms_part
        elif len(parts) == 2: # Format M:S.ms
            m = int(parts[0])
            s_ms_part = float(parts[1])
            total_seconds = m * 60 + s_ms_part
        elif len(parts) == 1: # Format S.ms or S
            s_ms_part = float(parts[0])
            total_seconds = s_ms_part
        else: # Invalid format
            return None
        return total_seconds
    except ValueError: # Handle non-numeric parts
        return None
        
# --------------------------------------------------------
# - Formatting Functions
#---------------------------------------------------------
# Formats total seconds into MM:SS.CS (centiseconds)
def format_duration_ms(total_seconds):
    if total_seconds is None or not isinstance(total_seconds, (int, float, Decimal)) or total_seconds < 0: # Validate input
        return "00:00.00"
    total_seconds_float = float(total_seconds) # Ensure float for calculations
    minutes = int(total_seconds_float // 60)
    remaining_seconds_component = total_seconds_float % 60
    seconds = int(remaining_seconds_component)
    centiseconds = int((remaining_seconds_component - seconds) * 100) # Calculate centiseconds
    return f"{minutes}:{seconds:02d}.{centiseconds:02d}"

# Formats total seconds into a human-readable string (Xd XXh:XXm:XXs)
def format_total_seconds_human_readable(total_seconds):
    if total_seconds is None or not isinstance(total_seconds, (int, float, Decimal)) or total_seconds < 0: # Validate input
        return "N/A"
    
    total_seconds = float(total_seconds) # Ensure float for consistent math

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
    elif days > 0: # Ensure hours are shown if days are present
         parts.append("00h")
    
    parts.append(f"{minutes:02d}m")
    parts.append(f"{seconds:02d}s")
    
    if not parts: # Default for zero duration
        return "00m:00s"
        
    return ":".join(parts)

# Formats total split seconds into M:SS.s (tenths of a second)
def format_split_short(total_split_seconds_raw):
    if total_split_seconds_raw is None or not isinstance(total_split_seconds_raw, (int, float, Decimal)) or total_split_seconds_raw <= 0: # Validate input
        return "N/A"
    
    total_split_seconds_raw = float(total_split_seconds_raw) # Ensure float for consistent math
    minutes = int(total_split_seconds_raw // 60)
    remaining_seconds_float = total_split_seconds_raw % 60
    
    # Calculate seconds and tenths of a second
    seconds_and_ms_combined_truncated = int(remaining_seconds_float * 10) 
    
    seconds_part = int(seconds_and_ms_combined_truncated // 10) 
    milliseconds_decimal_part = int(seconds_and_ms_combined_truncated % 10)

    return f"{minutes}:{seconds_part:02d}.{milliseconds_decimal_part}"

# Formats total seconds into a descriptive string e.g., "Xh Ym Zs".
# All components (hours, minutes, seconds) are always displayed.
def format_seconds_to_hms(total_seconds_input): # Renamed from format_duration_hms_tenths
    if total_seconds_input is None or not isinstance(total_seconds_input, (int, float, Decimal)) or total_seconds_input < 0:
        return "N/A"

    total_seconds_val = float(total_seconds_input)

    hrs = int(total_seconds_val // 3600)
    remaining_secs_after_hrs = total_seconds_val % 3600
    mins = int(remaining_secs_after_hrs // 60)
    secs = int(remaining_secs_after_hrs % 60) # Integer seconds

    if hrs > 0:
        return f"{hrs}h {mins:02d}m {secs:02d}s"
    else:
        return f"{mins:02d}m {secs:02d}s"

# --------------------------------------------------------
# - Custom Jinja2 Filters
#---------------------------------------------------------
# Converts newline characters in a string to HTML <br> tags.
def nl2br_filter(value):
    if value is None:
        return ''
    return Markup(str(value).replace('\n', '<br>\n'))

# --------------------------------------------------------
# - Context Processors
#---------------------------------------------------------
# Fetches overall rowing statistics for the sidebar
def sidebar_stats_processor():
    stats = {}
    try:
        with db.engine.connect() as connection:
            # Query materialized view for summed totals
            overall_totals_result = connection.execute(text("SELECT * FROM mv_sum_totals LIMIT 1")).fetchone()
            if overall_totals_result:
                stats['overall_totals'] = {
                    'meters': float(overall_totals_result.total_meters_rowed) if overall_totals_result.total_meters_rowed is not None else 0,
                    'seconds': float(overall_totals_result.total_seconds_rowed) if overall_totals_result.total_seconds_rowed is not None else 0,
                    'split': float(overall_totals_result.average_split_seconds_per_500m) if overall_totals_result.average_split_seconds_per_500m is not None else 0,
                    'isoreps': int(overall_totals_result.total_isoreps_sum) if overall_totals_result.total_isoreps_sum is not None else 0
                }
            else: # Handle empty materialized view
                stats['overall_totals'] = {'meters': 0, 'seconds': 0, 'split': 0, 'isoreps': 0}


    except Exception as e: # Catch potential database errors
        current_app.logger.error(f"Error fetching sidebar stats: {e}", exc_info=True)
        # Provide default stats on error
        stats = {
            'overall_totals': {'meters': 0, 'seconds': 0, 'split': 0, 'isoreps': 0},
        }
    
    return dict(sidebar_stats=stats) # Make stats available to templates

# Provides utility functions like 'now' to all templates
def utility_processor():
    return dict(now=datetime.datetime.now)

# --------------------------------------------------------
# - Custom Pagination Class
#---------------------------------------------------------
# Provides pagination logic for views not using Flask-SQLAlchemy's paginate().
class CustomPagination:
    # -- Initialization Method -------------------
    def __init__(self, page, per_page, total_count, items):
        self.page = page # Current page number
        self.per_page = per_page # Items per page
        self.total = total_count # Total number of items
        self.pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1 # Total number of pages
        self.has_prev = self.page > 1 # True if there's a previous page
        self.has_next = self.page < self.pages # True if there's a next page
        self.prev_num = self.page - 1 if self.has_prev else None # Previous page number
        self.next_num = self.page + 1 if self.has_next else None # Next page number
        self.items = items # The actual items for the current page

    # -- Page Iterator Method -------------------
    # Generates page numbers for pagination links, including ellipses.
    def iter_pages(self, left_edge=2, right_edge=2, left_current=2, right_current=3):
        last_page = 0
        for num in range(1, self.pages + 1):
            # Determine if the page number should be displayed
            if num <= left_edge or \
               (num > self.page - left_current - 1 and num < self.page + right_current) or \
               num > self.pages - right_edge:
                if last_page + 1 != num: # If there's a gap, yield None for ellipsis
                    yield None
                yield num # Yield the page number
                last_page = num