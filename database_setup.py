# ========================================================
# = database_setup.py - Functions for database setup and maintenance
# ========================================================
from flask import current_app # current_app is still needed for logger and db operations
from sqlalchemy import text
from models import db, UserSetting

# --------------------------------------------------------
# - Database Components Creation Function
#---------------------------------------------------------
# Creates all database tables, materialized views, functions, and triggers.
# Designed to be idempotent, meaning it can be run multiple times without adverse effects.
def create_db_components():
    try:
        # == Create SQLAlchemy Model Tables ============================================
        # Ensures all tables defined in models.py exist in the database.
        # This requires an app context.
        with current_app.app_context():
            db.create_all()
        current_app.logger.info("Database tables created (or ensured to exist) successfully!")

        # == SQL Definitions for Materialized Views and Triggers ============================================
        # -- SQL for Dropping Materialized Views (for idempotency) -------------------
        drop_mvs_sql = """
        DROP MATERIALIZED VIEW IF EXISTS mv_sum_totals;
        DROP MATERIALIZED VIEW IF EXISTS mv_year_totals;
        DROP MATERIALIZED VIEW IF EXISTS mv_month_totals;
        DROP MATERIALIZED VIEW IF EXISTS mv_week_totals;
        DROP MATERIALIZED VIEW IF EXISTS mv_day_totals;
        """

        # -- SQL for Creating Materialized Views -------------------
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
            END AS average_split_seconds_per_500m,
            SUM(w.total_isoreps) AS total_isoreps_sum
        FROM
            workouts w
        WHERE
            w.total_distance_meters IS NOT NULL AND w.duration_seconds IS NOT NULL 
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
            END AS average_split_seconds_per_500m,
            SUM(w.total_isoreps) AS total_isoreps_sum
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
            END AS average_split_seconds_per_500m,
            SUM(w.total_isoreps) AS total_isoreps_sum
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
            END AS average_split_seconds_per_500m,
            SUM(w.total_isoreps) AS total_isoreps_sum
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
            END AS average_split_seconds_per_500m,
            SUM(w.total_isoreps) AS total_isoreps_sum
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

        # -- SQL for Creating/Replacing Trigger Function -------------------
        create_function_sql = """
        CREATE OR REPLACE FUNCTION refresh_rowing_summary_mvs()
        RETURNS TRIGGER AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW mv_sum_totals;
            REFRESH MATERIALIZED VIEW mv_year_totals;
            REFRESH MATERIALIZED VIEW mv_month_totals;
            REFRESH MATERIALIZED VIEW mv_week_totals;
            REFRESH MATERIALIZED VIEW mv_day_totals;
            RETURN NULL; -- Result is ignored since this is an AFTER trigger
        END;
        $$ LANGUAGE plpgsql;
        """

        # -- SQL for Dropping and Creating Triggers -------------------
        drop_and_create_triggers_sql = """
        DROP TRIGGER IF EXISTS trg_refresh_rowing_summary_on_workout ON workouts;

        CREATE TRIGGER trg_refresh_rowing_summary_on_workout
        AFTER INSERT OR UPDATE OR DELETE ON workouts
        FOR EACH STATEMENT -- Important: refreshes once per statement, not per row
        EXECUTE FUNCTION refresh_rowing_summary_mvs();
        """

        # == Execute SQL Statements ============================================
        # Use a single transaction for all DDL operations.
        # This requires an app context for db.engine.
        with current_app.app_context():
            with db.engine.connect() as connection:
                with connection.begin(): # Start a transaction
                    current_app.logger.info("Executing DDL for materialized views and triggers...")
                    connection.execute(text(drop_mvs_sql))
                    connection.execute(text(create_mvs_sql))
                    connection.execute(text(create_function_sql))
                    connection.execute(text(drop_and_create_triggers_sql))
                    current_app.logger.info("Materialized views and triggers setup complete.")

                    # == Initialize Default Settings ============================================
                    current_app.logger.info("Initializing default settings...")
                    db_schema_ver_setting = db.session.query(UserSetting).filter_by(key='db_schema_ver').first()
                    if not db_schema_ver_setting:
                        initial_db_schema_version = "0.13" # Or your current version
                        new_setting = UserSetting(key='db_schema_ver', value=initial_db_schema_version)
                        db.session.add(new_setting)
                        db.session.commit()
                        current_app.logger.info(f"Initialized 'db_schema_ver' to '{initial_db_schema_version}'.")
                    else:
                        current_app.logger.info(f"'db_schema_ver' already exists with value '{db_schema_ver_setting.value}'. No changes made.")
            # Transaction for DDL is committed here if no exceptions
        
        current_app.logger.info("Database components and default settings set up successfully!")
        return True

    except Exception as e:
        current_app.logger.error(f"Error setting up database components: {e}", exc_info=True)
        return False
