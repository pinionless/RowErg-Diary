# ========================================================
# = rolling_avg.py - View for displaying rolling average pace
# ========================================================
from flask import Blueprint, render_template, current_app
from models import db
from sqlalchemy import text

rolling_avg_bp = Blueprint('rolling_avg', __name__, url_prefix='/rolling-avg')

# --------------------------------------------------------
# - Main Route
#---------------------------------------------------------
@rolling_avg_bp.route('/')
def index():
    """Renders a single combined Rolling Average pace chart."""
    try:
        # Fetch all precalculated values from the MV ordered chronologically
        query = text("""
            SELECT 
                workout_date,
                avg_all_time,
                avg_365_days,
                avg_180_days,
                avg_90_days,
                avg_30_days,
                avg_7_days
            FROM mv_rolling_avg
            ORDER BY workout_date, workout_id
        """)
        results = db.session.execute(query).fetchall()

        dates = []
        all_time = []
        last_365 = []
        last_180 = []
        last_90 = []
        last_30 = []
        last_7 = []

        for row in results:
            dates.append(row.workout_date.strftime('%Y-%m-%d'))
            all_time.append(round(float(row.avg_all_time), 2) if row.avg_all_time else None)
            last_365.append(round(float(row.avg_365_days), 2) if row.avg_365_days else None)
            last_180.append(round(float(row.avg_180_days), 2) if row.avg_180_days else None)
            last_90.append(round(float(row.avg_90_days), 2) if row.avg_90_days else None)
            last_30.append(round(float(row.avg_30_days), 2) if row.avg_30_days else None)
            last_7.append(round(float(row.avg_7_days), 2) if row.avg_7_days else None)

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
            'rolling_avg.html',
            page_title="Rolling Average Pace",
            chart_data=chart_data,
        )

    except Exception as e:
        current_app.logger.error(f"Error fetching rolling avg combined data: {e}", exc_info=True)
        return render_template(
            'rolling_avg.html',
            page_title="Rolling Average Pace",
            chart_data={'dates': [], 'series': []},
        )


# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
def register_routes(app):
    app.register_blueprint(rolling_avg_bp)
