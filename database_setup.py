# ========================================================
# = database_setup.py - Functions for database setup and maintenance
# ========================================================
from flask import current_app # current_app is still needed for logger and db operations
from sqlalchemy import text
from models import db, UserSetting

# Global SQL definition for dropping Materialized Views
DROP_MVS_SQL = """
DROP MATERIALIZED VIEW IF EXISTS mv_sum_totals;
DROP MATERIALIZED VIEW IF EXISTS mv_year_totals;
DROP MATERIALIZED VIEW IF EXISTS mv_month_totals;
DROP MATERIALIZED VIEW IF EXISTS mv_week_totals;
DROP MATERIALIZED VIEW IF EXISTS mv_day_totals;
"""

# Helper function to generate the CREATE MATERIALIZED VIEW SQL
def _get_create_mvs_sql():
    """
    Returns the SQL string for creating all materialized views with
    conditional aggregation based on equipment_types.settings_include_in_totals.
    """
    return f"""
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
        JOIN equipment_types et ON w.equipment_type_id = et.equipment_type_id
    WHERE
        w.total_distance_meters IS NOT NULL 
        AND w.duration_seconds IS NOT NULL
        AND et.settings_include_in_totals = TRUE
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
        JOIN equipment_types et ON w.equipment_type_id = et.equipment_type_id
    WHERE 
        w.total_distance_meters IS NOT NULL 
        AND w.duration_seconds IS NOT NULL
        AND et.settings_include_in_totals = TRUE
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
        JOIN equipment_types et ON w.equipment_type_id = et.equipment_type_id
    WHERE 
        w.total_distance_meters IS NOT NULL 
        AND w.duration_seconds IS NOT NULL
        AND et.settings_include_in_totals = TRUE
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
        JOIN equipment_types et ON w.equipment_type_id = et.equipment_type_id
    WHERE 
        w.total_distance_meters IS NOT NULL 
        AND w.duration_seconds IS NOT NULL
        AND et.settings_include_in_totals = TRUE
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
        JOIN equipment_types et ON w.equipment_type_id = et.equipment_type_id
    WHERE 
        w.total_distance_meters IS NOT NULL 
        AND w.duration_seconds IS NOT NULL
        AND et.settings_include_in_totals = TRUE
    GROUP BY
        w.workout_date
    ORDER BY
        day_date
    WITH DATA;
    """

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
        # -- SQL for Dropping Materialized Views (now global) -------------------
        # drop_mvs_sql is now DROP_MVS_SQL (global constant)

        # -- SQL for Creating Materialized Views (now from helper) -------------------
        create_mvs_sql = _get_create_mvs_sql()

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
        DROP TRIGGER IF EXISTS trg_refresh_summary_on_equipment_update ON equipment_types;

        CREATE TRIGGER trg_refresh_rowing_summary_on_workout
        AFTER INSERT OR UPDATE OR DELETE ON workouts
        FOR EACH STATEMENT 
        EXECUTE FUNCTION refresh_rowing_summary_mvs();

        CREATE TRIGGER trg_refresh_summary_on_equipment_update
        AFTER UPDATE ON equipment_types
        FOR EACH STATEMENT
        EXECUTE FUNCTION refresh_rowing_summary_mvs();
        """

        # == Execute SQL Statements ============================================
        # Use a single transaction for all DDL operations.
        # This requires an app context for db.engine.
        with current_app.app_context():
            with db.engine.connect() as connection:
                with connection.begin(): # Start a transaction
                    current_app.logger.info("Executing DDL for materialized views and triggers...")
                    connection.execute(text(DROP_MVS_SQL)) # Use global constant
                    connection.execute(text(create_mvs_sql)) # Use SQL from helper
                    connection.execute(text(create_function_sql))
                    connection.execute(text(drop_and_create_triggers_sql))
                    current_app.logger.info("Materialized views and triggers setup complete.")

                    # == Initialize Default Settings ============================================
                    current_app.logger.info("Initializing default settings...")
                    
                    default_settings = {
                        'db_schema_ver': current_app.config.get('TARGET_DB_SCHEMA_VERSION', '0.0'),
                        'per_page_workouts': '20',
                        'per_page_summary_day': '14',
                        'per_page_summary_week': '12',
                        'per_page_summary_month': '12'
                    }

                    for key, value in default_settings.items():
                        setting_exists = db.session.query(UserSetting).filter_by(key=key).first()
                        if not setting_exists:
                            new_setting = UserSetting(key=key, value=value)
                            db.session.add(new_setting)
                            current_app.logger.info(f"Initialized setting '{key}' to '{value}'.")
                        else:
                            current_app.logger.info(f"Setting '{key}' already exists with value '{setting_exists.value}'. No changes made by create_db_components for this key.")
                    
                    db.session.commit() # Commit all new settings
            # Transaction for DDL is committed here if no exceptions
        
        current_app.logger.info("Database components and default settings set up successfully!")
        return True

    except Exception as e:
        current_app.logger.error(f"Error setting up database components: {e}", exc_info=True)
        return False

# --------------------------------------------------------
# - Database Schema Update Function (Placeholder)
#---------------------------------------------------------
def update_db_schema(current_version, target_version):
    current_app.logger.info(f"Attempting to update database schema from {current_version} to {target_version}.")
    
    # Make a mutable copy of current_version to track progress within the loop
    effective_current_version = current_version

    with current_app.app_context():
        while effective_current_version != target_version:
            applied_migration_in_iteration = False
            if effective_current_version == "0.13" and target_version >= "0.15": # Check against target_version
                current_app.logger.info("Applying schema migration from 0.13 to 0.15.")
                try:
                    # 1. Add 'settings_include_in_totals' column
                    current_app.logger.info("Adding 'settings_include_in_totals' to 'equipment_types'.")
                    alter_sql = text("""
                        ALTER TABLE equipment_types
                        ADD COLUMN IF NOT EXISTS settings_include_in_totals BOOLEAN NOT NULL DEFAULT TRUE;
                    """)
                    with db.engine.connect() as connection:
                        with connection.begin(): # Start a transaction for this 
                            connection.execute(alter_sql)
                        # DDL transaction committed

                    # 2. Add new default user settings
                    current_app.logger.info("Adding default pagination settings to 'user_settings'.")
                    default_pagination_settings = {
                        'per_page_workouts': '20',
                        'per_page_summary_day': '14',
                        'per_page_summary_week': '12',
                        'per_page_summary_month': '12'
                    }
                    for key, value in default_pagination_settings.items():
                        setting_exists = db.session.query(UserSetting).filter_by(key=key).first()
                        if not setting_exists:
                            new_setting = UserSetting(key=key, value=value)
                            db.session.add(new_setting)
                            current_app.logger.info(f"Added default setting during migration: '{key}' = '{value}'.")
                    
                    # 3. Update the schema version in the database
                    migrated_to_version = "0.15"
                    setting = db.session.query(UserSetting).filter_by(key='db_schema_ver').first()
                    if setting:
                        setting.value = migrated_to_version
                        db.session.add(setting) 
                        current_app.logger.info(f"Updated 'db_schema_ver' to '{migrated_to_version}'.")
                    else:
                        current_app.logger.error(f"Could not find 'db_schema_ver' to update during migration to {migrated_to_version}. Creating it.")
                        new_schema_ver_setting = UserSetting(key='db_schema_ver', value=migrated_to_version)
                        db.session.add(new_schema_ver_setting)

                    db.session.commit() 
                    current_app.logger.info(f"Database schema migration from 0.13 to {migrated_to_version} completed successfully.")
                    effective_current_version = migrated_to_version
                    applied_migration_in_iteration = True
                            
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Error migrating schema from 0.13 to 0.15: {e}", exc_info=True)
                    return # Stop further migrations on error
            
            elif effective_current_version == "0.15" and target_version >= "0.16": # Check against target_version
                current_app.logger.info("Applying schema migration from 0.15 to 0.16 (Update Materialized Views and Triggers).")
                try:
                    # Define the SQL for triggers, ensuring it includes both.
                    # This is the same definition as in create_db_components.
                    final_drop_and_create_triggers_sql = """
                    DROP TRIGGER IF EXISTS trg_refresh_rowing_summary_on_workout ON workouts;
                    DROP TRIGGER IF EXISTS trg_refresh_summary_on_equipment_update ON equipment_types;

                    CREATE TRIGGER trg_refresh_rowing_summary_on_workout
                    AFTER INSERT OR UPDATE OR DELETE ON workouts
                    FOR EACH STATEMENT 
                    EXECUTE FUNCTION refresh_rowing_summary_mvs();

                    CREATE TRIGGER trg_refresh_summary_on_equipment_update
                    AFTER UPDATE ON equipment_types
                    FOR EACH STATEMENT
                    EXECUTE FUNCTION refresh_rowing_summary_mvs();
                    """
                    with db.engine.connect() as connection:
                        with connection.begin(): # Start a transaction for DDL
                            current_app.logger.info("Dropping existing materialized views...")
                            connection.execute(text(DROP_MVS_SQL))
                            current_app.logger.info("Creating new materialized views with updated definitions...")
                            connection.execute(text(_get_create_mvs_sql()))
                            current_app.logger.info("Dropping and recreating triggers to include equipment_types and workouts.")
                            connection.execute(text(final_drop_and_create_triggers_sql))
                    
                    migrated_to_version = "0.16"
                    # Update the schema version in the database
                    setting = db.session.query(UserSetting).filter_by(key='db_schema_ver').first()
                    if setting:
                        setting.value = migrated_to_version
                        db.session.add(setting)
                        current_app.logger.info(f"Updated 'db_schema_ver' to '{migrated_to_version}'.")
                    else:
                        current_app.logger.error(f"Could not find 'db_schema_ver' to update during migration to {migrated_to_version}. Creating it.")
                        new_schema_ver_setting = UserSetting(key='db_schema_ver', value=migrated_to_version)
                        db.session.add(new_schema_ver_setting)

                    db.session.commit() 
                    current_app.logger.info(f"Database schema migration from 0.15 to {migrated_to_version} completed successfully.")
                    effective_current_version = migrated_to_version
                    applied_migration_in_iteration = True

                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Error migrating schema from 0.15 to 0.16: {e}", exc_info=True)
                    return # Stop further migrations on error
            


            if not applied_migration_in_iteration:
                # If no migration was applied in this iteration, it means we're stuck or target is met.
                # The while loop condition (effective_current_version != target_version) will handle the target met case.
                # If stuck, log and break to prevent infinite loop.
                if effective_current_version != target_version: # Only log if there's an actual mismatch not handled
                    current_app.logger.warning(f"No specific migration path found from {effective_current_version} to {target_version}. Stopping migration process.")
                break 
        
        if effective_current_version == target_version:
            current_app.logger.info(f"All schema migrations up to version {target_version} completed successfully.")
        else:
            current_app.logger.warning(f"Schema migration process stopped at version {effective_current_version}, but target was {target_version}.")
