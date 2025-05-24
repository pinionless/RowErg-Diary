# database_management.py
from flask import redirect, url_for, flash, current_app
from models import db # Assuming db is initialized and available
from sqlalchemy import text # Import text for raw SQL execution

def create_db_components():
    """
    Creates all database tables, materialized views, functions, and triggers.
    Designed to be idempotent.
    """
    try:
        # 1. Create all tables defined in Flask-SQLAlchemy models
        db.create_all()
        flash("Database tables created (or ensured to exist) successfully!", "success")

        # --- SQL for Dropping Materialized Views (for idempotency) ---
        drop_mvs_sql = """
        DROP MATERIALIZED VIEW IF EXISTS mv_sum_totals;
        DROP MATERIALIZED VIEW IF EXISTS mv_year_totals;
        DROP MATERIALIZED VIEW IF EXISTS mv_month_totals;
        DROP MATERIALIZED VIEW IF EXISTS mv_week_totals;
        DROP MATERIALIZED VIEW IF EXISTS mv_day_totals;
        """

        # --- SQL for Creating Materialized Views (with unit conversion for Duration) ---
        duration_conversion_case = """
            CASE
                WHEN ws.property_key = 'Duration' AND (ws.unit_of_measure = 'minutes' OR ws.unit_of_measure = 'min') THEN ws.raw_value * 60
                WHEN ws.property_key = 'Duration' AND ws.unit_of_measure = 'hours' THEN ws.raw_value * 3600
                WHEN ws.property_key = 'Duration' AND ws.unit_of_measure = 'milliseconds' THEN ws.raw_value / 1000.0
                WHEN ws.property_key = 'Duration' AND (ws.unit_of_measure = 'seconds' OR ws.unit_of_measure IS NULL OR ws.unit_of_measure = '') THEN ws.raw_value
                ELSE 0
            END
        """

        # --- Corrected MV_WEEK_TOTALS for Monday as 1st day of week (assuming PostgreSQL config) ---
        create_mvs_sql = f"""
        CREATE MATERIALIZED VIEW mv_sum_totals AS
        SELECT
            SUM(CASE WHEN ws.property_key = 'derivedTotalDistance' THEN ws.raw_value ELSE 0 END) AS total_meters_rowed,
            SUM({duration_conversion_case}) AS total_seconds_rowed,
            CASE
                WHEN SUM(CASE WHEN ws.property_key = 'derivedTotalDistance' THEN ws.raw_value ELSE 0 END) > 0 THEN
                    SUM({duration_conversion_case}) / (SUM(CASE WHEN ws.property_key = 'derivedTotalDistance' THEN ws.raw_value ELSE 0 END) / 500.0)
                ELSE
                    0
            END AS average_split_seconds_per_500m
        FROM
            workout_summary_data ws
        JOIN
            workouts w ON ws.workout_id = w.workout_id
        WHERE
            ws.property_key IN ('derivedTotalDistance', 'Duration')
        WITH DATA;

        CREATE MATERIALIZED VIEW mv_year_totals AS
        SELECT
            EXTRACT(YEAR FROM w.workout_date) AS year,
            SUM(CASE WHEN ws.property_key = 'derivedTotalDistance' THEN ws.raw_value ELSE 0 END) AS total_meters_rowed,
            SUM({duration_conversion_case}) AS total_seconds_rowed,
            CASE
                WHEN SUM(CASE WHEN ws.property_key = 'derivedTotalDistance' THEN ws.raw_value ELSE 0 END) > 0 THEN
                    SUM({duration_conversion_case}) / (SUM(CASE WHEN ws.property_key = 'derivedTotalDistance' THEN ws.raw_value ELSE 0 END) / 500.0)
                ELSE
                    0
            END AS average_split_seconds_per_500m
        FROM
            workout_summary_data ws
        JOIN
            workouts w ON ws.workout_id = w.workout_id
        WHERE
            ws.property_key IN ('derivedTotalDistance', 'Duration')
        GROUP BY
            EXTRACT(YEAR FROM w.workout_date)
        ORDER BY
            year
        WITH DATA;

        CREATE MATERIALIZED VIEW mv_month_totals AS
        SELECT
            EXTRACT(YEAR FROM w.workout_date) AS year,
            EXTRACT(MONTH FROM w.workout_date) AS month,
            SUM(CASE WHEN ws.property_key = 'derivedTotalDistance' THEN ws.raw_value ELSE 0 END) AS total_meters_rowed,
            SUM({duration_conversion_case}) AS total_seconds_rowed,
            CASE
                WHEN SUM(CASE WHEN ws.property_key = 'derivedTotalDistance' THEN ws.raw_value ELSE 0 END) > 0 THEN
                    SUM({duration_conversion_case}) / (SUM(CASE WHEN ws.property_key = 'derivedTotalDistance' THEN ws.raw_value ELSE 0 END) / 500.0)
                ELSE
                    0
            END AS average_split_seconds_per_500m
        FROM
            workout_summary_data ws
        JOIN
            workouts w ON ws.workout_id = w.workout_id
        WHERE
            ws.property_key IN ('derivedTotalDistance', 'Duration')
        GROUP BY
            EXTRACT(YEAR FROM w.workout_date),
            EXTRACT(MONTH FROM w.workout_date)
        ORDER BY
            year, month
        WITH DATA;

        CREATE MATERIALIZED VIEW mv_week_totals AS
        SELECT
            DATE_TRUNC('week', w.workout_date)::date AS week_start_date, -- SIMPLIFIED FORMULA HERE (ASSUMES PG IS CONFIGURED FOR MONDAY START)
            SUM(CASE WHEN ws.property_key = 'derivedTotalDistance' THEN ws.raw_value ELSE 0 END) AS total_meters_rowed,
            SUM({duration_conversion_case}) AS total_seconds_rowed,
            CASE
                WHEN SUM(CASE WHEN ws.property_key = 'derivedTotalDistance' THEN ws.raw_value ELSE 0 END) > 0 THEN
                    SUM({duration_conversion_case}) / (SUM(CASE WHEN ws.property_key = 'derivedTotalDistance' THEN ws.raw_value ELSE 0 END) / 500.0)
                ELSE
                    0
            END AS average_split_seconds_per_500m
        FROM
            workout_summary_data ws
        JOIN
            workouts w ON ws.workout_id = w.workout_id
        WHERE
            ws.property_key IN ('derivedTotalDistance', 'Duration')
        GROUP BY
            DATE_TRUNC('week', w.workout_date)::date
        ORDER BY
            week_start_date
        WITH DATA;

        CREATE MATERIALIZED VIEW mv_day_totals AS
        SELECT
            w.workout_date AS day_date,
            SUM(CASE WHEN ws.property_key = 'derivedTotalDistance' THEN ws.raw_value ELSE 0 END) AS total_meters_rowed,
            SUM({duration_conversion_case}) AS total_seconds_rowed,
            CASE
                WHEN SUM(CASE WHEN ws.property_key = 'derivedTotalDistance' THEN ws.raw_value ELSE 0 END) > 0 THEN
                    SUM({duration_conversion_case}) / (SUM(CASE WHEN ws.property_key = 'derivedTotalDistance' THEN ws.raw_value ELSE 0 END) / 500.0)
                ELSE
                    0
            END AS average_split_seconds_per_500m
        FROM
            workout_summary_data ws
        JOIN
            workouts w ON ws.workout_id = w.workout_id
        WHERE
            ws.property_key IN ('derivedTotalDistance', 'Duration')
        GROUP BY
            w.workout_date
        ORDER BY
            day_date
        WITH DATA;
        """

        # --- SQL for Creating/Replacing Trigger Function ---
        create_function_sql = """
        CREATE OR REPLACE FUNCTION refresh_rowing_summary_mvs()
        RETURNS TRIGGER AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW mv_sum_totals;
            REFRESH MATERIALIZED VIEW mv_year_totals;
            REFRESH MATERIALIZED VIEW mv_month_totals;
            REFRESH MATERIALIZED VIEW mv_week_totals;
            REFRESH MATERIALIZED VIEW mv_day_totals;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """

        # --- SQL for Dropping and Creating Triggers (for idempotency and creation) ---
        drop_and_create_triggers_sql = """
        DROP TRIGGER IF EXISTS trg_refresh_rowing_summary_on_workout ON workouts;
        DROP TRIGGER IF EXISTS trg_refresh_rowing_summary_on_summary_data ON workout_summary_data;

        CREATE TRIGGER trg_refresh_rowing_summary_on_workout
        AFTER INSERT OR UPDATE OR DELETE ON workouts
        FOR EACH STATEMENT
        EXECUTE FUNCTION refresh_rowing_summary_mvs();

        CREATE TRIGGER trg_refresh_rowing_summary_on_summary_data
        AFTER INSERT OR UPDATE OR DELETE ON workout_summary_data
        FOR EACH STATEMENT
        EXECUTE FUNCTION refresh_rowing_summary_mvs();
        """

        # 3. Execute the raw SQL commands within a database connection
        with db.engine.connect() as connection:
            with connection.begin():
                current_app.logger.info("Executing DDL for materialized views and triggers...")
                connection.execute(text(drop_mvs_sql))
                connection.execute(text(create_mvs_sql))
                connection.execute(text(create_function_sql))
                connection.execute(text(drop_and_create_triggers_sql))
                current_app.logger.info("Materialized views and triggers setup complete.")

        flash("Materialized views and triggers set up successfully!", "success")

    except Exception as e:
        current_app.logger.error(f"Error setting up database components: {e}", exc_info=True)
        flash(f"Error setting up database components: {str(e)}", "danger")

    return redirect(url_for('home'))


def delete_db_components():
    """
    Deletes all database components including triggers, materialized views, and tables.
    Designed for development convenience to clear the database entirely.
    Order of operations is crucial for dependencies.
    """
    try:
        # Define SQL to drop triggers, function, and materialized views
        drop_triggers_sql = """
        DROP TRIGGER IF EXISTS trg_refresh_rowing_summary_on_workout ON workouts;
        DROP TRIGGER IF EXISTS trg_refresh_rowing_summary_on_summary_data ON workout_summary_data;
        """

        drop_function_sql = """
        DROP FUNCTION IF EXISTS refresh_rowing_summary_mvs();
        """

        drop_mvs_sql_reverse_order = """
        DROP MATERIALIZED VIEW IF EXISTS mv_day_totals;
        DROP MATERIALIZED VIEW IF EXISTS mv_week_totals;
        DROP MATERIALIZED VIEW IF EXISTS mv_month_totals;
        DROP MATERIALIZED VIEW IF EXISTS mv_year_totals;
        DROP MATERIALIZED VIEW IF EXISTS mv_sum_totals;
        """

        with db.engine.connect() as connection:
            with connection.begin():
                current_app.logger.info("Executing DDL for dropping database components...")

                # 1. Drop Triggers first (they depend on tables and the function)
                connection.execute(text(drop_triggers_sql))
                current_app.logger.info("Dropped triggers.")

                # 2. Drop the Trigger Function (it depends on nothing, but triggers depend on it)
                connection.execute(text(drop_function_sql))
                current_app.logger.info("Dropped trigger function.")

                # 3. Drop Materialized Views (they depend on underlying tables)
                connection.execute(text(drop_mvs_sql_reverse_order))
                current_app.logger.info("Dropped materialized views.")

        # 4. Drop all Flask-SQLAlchemy managed tables
        db.drop_all()
        current_app.logger.info("Dropped all Flask-SQLAlchemy tables.")

        flash("All database components (tables, views, triggers) deleted successfully!", "success")

    except Exception as e:
        current_app.logger.error(f"Error deleting database components: {e}", exc_info=True)
        flash(f"Error deleting database components: {str(e)}", "danger")

    return redirect(url_for('home'))


def register_routes(app):
    """
    Registers the database management routes with the Flask application.
    """
    app.add_url_rule('/database/create', endpoint='create_db', view_func=create_db_components, methods=['GET'])
    app.add_url_rule('/database/delete', endpoint='delete_db', view_func=delete_db_components, methods=['GET'])