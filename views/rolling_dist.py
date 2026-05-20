# ========================================================
# = rolling_dist.py - View for displaying rolling average distance
# ========================================================
from flask import Blueprint, render_template, current_app, request
from models import db
from sqlalchemy import text

rolling_dist_bp = Blueprint('rolling_dist', __name__, url_prefix='/rolling-dist')

# --------------------------------------------------------
# - Main Route
#---------------------------------------------------------
@rolling_dist_bp.route('/')
def index():
    """Renders a single combined Rolling Average distance chart with filtering."""
    try:
        # -- Parse filter params -------------------
        range_filter = request.args.get('range', 'all')  # 'all', 'year', 'last'
        year_value = request.args.get('year', None, type=int)
        days_value = request.args.get('days', None, type=int)

        # -- Get available years for buttons -------------------
        years_query = text("""
            SELECT DISTINCT EXTRACT(YEAR FROM workout_date)::integer AS yr
            FROM mv_rolling_dist
            ORDER BY yr DESC
        """)
        available_years = [row.yr for row in db.session.execute(years_query).fetchall()]

        # -- Build filtered query -------------------
        if range_filter == 'year' and year_value:
            query = text("""
                SELECT workout_date, avg_all_time, avg_365_days, avg_180_days,
                       avg_90_days, avg_30_days, avg_7_days
                FROM mv_rolling_dist
                WHERE EXTRACT(YEAR FROM workout_date) = :year
                ORDER BY workout_date
            """)
            results = db.session.execute(query, {'year': year_value}).fetchall()
            page_title = f"Rolling Average Distance — {year_value}"

        elif range_filter == 'last' and days_value:
            query = text("""
                SELECT workout_date, avg_all_time, avg_365_days, avg_180_days,
                       avg_90_days, avg_30_days, avg_7_days
                FROM mv_rolling_dist
                WHERE workout_date >= CURRENT_DATE - :days
                ORDER BY workout_date
            """)
            results = db.session.execute(query, {'days': days_value}).fetchall()
            page_title = f"Rolling Average Distance — Last {days_value} Days"

        else:
            # Default: all time
            query = text("""
                SELECT workout_date, avg_all_time, avg_365_days, avg_180_days,
                       avg_90_days, avg_30_days, avg_7_days
                FROM mv_rolling_dist
                ORDER BY workout_date
            """)
            results = db.session.execute(query).fetchall()
            page_title = "Rolling Average Distance"

        # -- Build chart data -------------------
        dates = []
        all_time = []
        last_365 = []
        last_180 = []
        last_90 = []
        last_30 = []
        last_7 = []

        for row in results:
            dates.append(row.workout_date.strftime('%Y-%m-%d'))
            all_time.append(round(float(row.avg_all_time), 0) if row.avg_all_time else None)
            last_365.append(round(float(row.avg_365_days), 0) if row.avg_365_days else None)
            last_180.append(round(float(row.avg_180_days), 0) if row.avg_180_days else None)
            last_90.append(round(float(row.avg_90_days), 0) if row.avg_90_days else None)
            last_30.append(round(float(row.avg_30_days), 0) if row.avg_30_days else None)
            last_7.append(round(float(row.avg_7_days), 0) if row.avg_7_days else None)

        chart_data = {
            'dates': dates,
            'series': [
                {'name': 'All Time', 'data': all_time},
                {'name': 'Last 365 Days', 'data': last_365},
                {'name': 'Last 180 Days', 'data': last_180},
                {'name': 'Last 90 Days', 'data': last_90},
                {'name': 'Last 30 Days', 'data': last_30},
                {'name': 'Last 7 Days', 'data': last_7},
            ]
        }

        return render_template(
            'rolling_dist.html',
            page_title=page_title,
            chart_data=chart_data,
            available_years=available_years,
            range_filter=range_filter,
            year_value=year_value,
            days_value=days_value,
        )

    except Exception as e:
        current_app.logger.error(f"Error fetching rolling dist combined data: {e}", exc_info=True)
        return render_template(
            'rolling_dist.html',
            page_title="Rolling Average Distance",
            chart_data={'dates': [], 'series': []},
            available_years=[],
            range_filter='all',
            year_value=None,
            days_value=None,
        )


# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
def register_routes(app):
    app.register_blueprint(rolling_dist_bp)
