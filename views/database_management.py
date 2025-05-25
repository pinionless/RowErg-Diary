# views/database_management.py
from flask import redirect, url_for, flash, current_app
from models import db # WorkoutSummaryData is no longer in models
from sqlalchemy import text

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

        # --- SQL for Creating Materialized Views ---
        # duration_conversion_case is no longer needed as duration_seconds is stored directly.
        create_mvs_sql = f"""
        CREATE MATERIALIZED VIEW mv_sum_totals AS
        SELECT
            SUM(w.total_distance_meters) AS total_meters_rowed,
            SUM(w.duration_seconds) AS total_seconds_rowed,
            CASE
                WHEN SUM(w.total_distance_meters) > 0 AND SUM(w.duration_seconds) > 0 THEN
                    SUM(w.duration_seconds) / (SUM(w.total_distance_meters) / 500.0)
                ELSE
                    0
            END AS average_split_seconds_per_500m
        FROM
            workouts w
        WHERE
            w.total_distance_meters IS NOT NULL AND w.duration_seconds IS NOT NULL 
            -- Optionally filter out workouts where these values are NULL if they shouldn't contribute to totals
        WITH DATA;

        CREATE MATERIALIZED VIEW mv_year_totals AS
        SELECT
            EXTRACT(YEAR FROM w.workout_date) AS year,
            SUM(w.total_distance_meters) AS total_meters_rowed,
            SUM(w.duration_seconds) AS total_seconds_rowed,
            CASE
                WHEN SUM(w.total_distance_meters) > 0 AND SUM(w.duration_seconds) > 0 THEN
                    SUM(w.duration_seconds) / (SUM(w.total_distance_meters) / 500.0)
                ELSE
                    0
            END AS average_split_seconds_per_500m
        FROM
            workouts w
        WHERE 
            w.total_distance_meters IS NOT NULL AND w.duration_seconds IS NOT NULL
        GROUP BY
            EXTRACT(YEAR FROM w.workout_date)
        ORDER BY
            year
        WITH DATA;

        CREATE MATERIALIZED VIEW mv_month_totals AS
        SELECT
            EXTRACT(YEAR FROM w.workout_date) AS year,
            EXTRACT(MONTH FROM w.workout_date) AS month,
            SUM(w.total_distance_meters) AS total_meters_rowed,
            SUM(w.duration_seconds) AS total_seconds_rowed,
            CASE
                WHEN SUM(w.total_distance_meters) > 0 AND SUM(w.duration_seconds) > 0 THEN
                    SUM(w.duration_seconds) / (SUM(w.total_distance_meters) / 500.0)
                ELSE
                    0
            END AS average_split_seconds_per_500m
        FROM
            workouts w
        WHERE 
            w.total_distance_meters IS NOT NULL AND w.duration_seconds IS NOT NULL
        GROUP BY
            EXTRACT(YEAR FROM w.workout_date),
            EXTRACT(MONTH FROM w.workout_date)
        ORDER BY
            year, month
        WITH DATA;

        CREATE MATERIALIZED VIEW mv_week_totals AS
        SELECT
            DATE_TRUNC('week', w.workout_date)::date AS week_start_date,
            SUM(w.total_distance_meters) AS total_meters_rowed,
            SUM(w.duration_seconds) AS total_seconds_rowed,
            CASE
                WHEN SUM(w.total_distance_meters) > 0 AND SUM(w.duration_seconds) > 0 THEN
                    SUM(w.duration_seconds) / (SUM(w.total_distance_meters) / 500.0)
                ELSE
                    0
            END AS average_split_seconds_per_500m
        FROM
            workouts w
        WHERE 
            w.total_distance_meters IS NOT NULL AND w.duration_seconds IS NOT NULL
        GROUP BY
            DATE_TRUNC('week', w.workout_date)::date
        ORDER BY
            week_start_date
        WITH DATA;

        CREATE MATERIALIZED VIEW mv_day_totals AS
        SELECT
            w.workout_date AS day_date,
            SUM(w.total_distance_meters) AS total_meters_rowed,
            SUM(w.duration_seconds) AS total_seconds_rowed,
            CASE
                WHEN SUM(w.total_distance_meters) > 0 AND SUM(w.duration_seconds) > 0 THEN
                    SUM(w.duration_seconds) / (SUM(w.total_distance_meters) / 500.0)
                ELSE
                    0
            END AS average_split_seconds_per_500m
        FROM
            workouts w
        WHERE 
            w.total_distance_meters IS NOT NULL AND w.duration_seconds IS NOT NULL
        GROUP BY
            w.workout_date
        ORDER BY
            day_date
        WITH DATA;
        """

        # --- SQL for Creating/Replacing Trigger Function (function itself is unchanged) ---
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

        # --- SQL for Dropping and Creating Triggers ---
        # Removed trigger for workout_summary_data
        drop_and_create_triggers_sql = """
        DROP TRIGGER IF EXISTS trg_refresh_rowing_summary_on_workout ON workouts;
        -- DROP TRIGGER IF EXISTS trg_refresh_rowing_summary_on_summary_data ON workout_summary_data; -- This line is removed

        CREATE TRIGGER trg_refresh_rowing_summary_on_workout
        AFTER INSERT OR UPDATE OR DELETE ON workouts
        FOR EACH STATEMENT
        EXECUTE FUNCTION refresh_rowing_summary_mvs();

        -- CREATE TRIGGER trg_refresh_rowing_summary_on_summary_data ... -- This block is removed
        """

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
    """
    try:
        drop_triggers_sql = """
        DROP TRIGGER IF EXISTS trg_refresh_rowing_summary_on_workout ON workouts;
        -- DROP TRIGGER IF EXISTS trg_refresh_rowing_summary_on_summary_data ON workout_summary_data; -- Removed
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
                connection.execute(text(drop_triggers_sql))
                current_app.logger.info("Dropped triggers.")
                connection.execute(text(drop_function_sql))
                current_app.logger.info("Dropped trigger function.")
                connection.execute(text(drop_mvs_sql_reverse_order))
                current_app.logger.info("Dropped materialized views.")

        db.drop_all() # This will drop WorkoutSummaryData table if it still exists due to old schema
        current_app.logger.info("Dropped all Flask-SQLAlchemy tables.")

        flash("All database components (tables, views, triggers) deleted successfully!", "success")

    except Exception as e:
        current_app.logger.error(f"Error deleting database components: {e}", exc_info=True)
        flash(f"Error deleting database components: {str(e)}", "danger")

    return redirect(url_for('home'))


def register_routes(app):
    app.add_url_rule('/database/create', endpoint='create_db', view_func=create_db_components, methods=['GET'])
    app.add_url_rule('/database/delete', endpoint='delete_db', view_func=delete_db_components, methods=['GET'])