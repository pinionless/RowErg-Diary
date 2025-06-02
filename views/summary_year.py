# ========================================================
# = summary_year.py - View for displaying yearly workout summaries
# ========================================================
from flask import render_template, redirect, url_for, current_app
from sqlalchemy import text
from models import db 
from utils import CustomPagination 
import math # Import math for isnan and isfinite

# --------------------------------------------------------
# - Yearly Summary View Function
#---------------------------------------------------------
# Displays paginated yearly workout summaries from the mv_year_totals materialized view.
def summary_year(): # Renamed function
    # == Query Data for Current Page ============================================
    summary_year_raw_results = db.session.execute(text("""
        SELECT
            year,
            total_meters_rowed,
            total_seconds_rowed,
            average_split_seconds_per_500m AS split,
            total_isoreps_sum
        FROM
            mv_year_totals
        ORDER BY
            year DESC
    """)).fetchall()

    # == Prepare Data for Template ============================================
    summary_year_display_data = [] # Renamed variable
    for row in summary_year_raw_results:
        summary_year_display_data.append({ # Renamed variable
            'year': int(row.year),
            'meters': float(row.total_meters_rowed) if row.total_meters_rowed is not None else 0,
            'seconds': float(row.total_seconds_rowed) if row.total_seconds_rowed is not None else 0,
            'split': float(row.split) if row.split is not None else 0,
            'isoreps': float(row.total_isoreps_sum) if row.total_isoreps_sum is not None else 0
        })

    # == Prepare Data for Chart (New Structure) ============================================
    # Data for the table is year DESC. For chart, typically year ASC (left to right).
    chart_categories_years = []
    series_data_meters = []
    series_data_seconds = []
    series_data_pace = []
    series_data_reps = [] # Renamed from series_data_isoreps

    if summary_year_display_data: # Renamed variable
        # Create a new list sorted by year ascending for the chart
        chart_source_data = sorted(summary_year_display_data, key=lambda x: x['year']) # Renamed variable
        chart_categories_years = [str(item['year']) for item in chart_source_data]
        
        # Sanitize series data: replace NaN/Infinity with None (JSON null)
        series_data_meters = [
            item['meters'] if isinstance(item['meters'], (int, float)) and math.isfinite(item['meters']) else None 
            for item in chart_source_data
        ]
        series_data_seconds = [
            item['seconds'] if isinstance(item['seconds'], (int, float)) and math.isfinite(item['seconds']) else None
            for item in chart_source_data
        ]
        series_data_pace = [
            item['split'] if isinstance(item['split'], (int, float)) and math.isfinite(item['split']) and item['split'] > 0 else None
            for item in chart_source_data
        ]
        series_data_reps = [ # Renamed from series_data_isoreps
            item['isoreps'] if isinstance(item['isoreps'], (int, float)) and math.isfinite(item['isoreps']) else None
            for item in chart_source_data
        ]

    # == Render Template ============================================
    return render_template(
        'summary_year.html', # Updated template name
        summary_year_display_data=summary_year_display_data, # Renamed variable
        page_title="Yearly Workout Summaries",
        # New chart data variables
        chart_categories_years=chart_categories_years,
        series_data_meters=series_data_meters,
        series_data_seconds=series_data_seconds,
        series_data_pace=series_data_pace,
        series_data_reps=series_data_reps, # Renamed from series_data_isoreps
        has_chart_data=bool(summary_year_display_data) # Keep this for conditional rendering (renamed variable)
    )

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the yearly summary view routes with the Flask application.
def register_routes(app):
    app.add_url_rule('/summary_year/', endpoint='summary_year', view_func=summary_year, methods=['GET']) # Updated endpoint and view_func