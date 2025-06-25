# ========================================================
# = database_setup.py - Functions for database setup and maintenance
# ========================================================
from flask import current_app # current_app is still needed for logger and db operations
from sqlalchemy import text
from models import db, UserSetting, EquipmentType, RankingSetting # Added RankingSetting

# Global SQL definition for dropping Materialized Views
DROP_MVS_SQL = """
DROP MATERIALIZED VIEW IF EXISTS mv_sum_totals;
DROP MATERIALIZED VIEW IF EXISTS mv_year_totals;
DROP MATERIALIZED VIEW IF EXISTS mv_month_totals;
DROP MATERIALIZED VIEW IF EXISTS mv_week_totals;
DROP MATERIALIZED VIEW IF EXISTS mv_day_totals;
DROP MATERIALIZED VIEW IF EXISTS mv_workout_rankings;
"""

# Global SQL definition for dropping functions
DROP_FUNCTIONS_SQL = """
DROP FUNCTION IF EXISTS refresh_rowing_summary_mvs() CASCADE;
DROP FUNCTION IF EXISTS refresh_workout_rankings_mv() CASCADE;
"""

# -- SQL for Creating/Replacing Trigger Function (summary MVs only) -------------------
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

# -- SQL for Creating/Replacing Trigger Function (ranking MV only) -------------------
create_function_ranking_sql = """
CREATE OR REPLACE FUNCTION refresh_workout_rankings_mv()
RETURNS TRIGGER AS $$
BEGIN
    REFRESH MATERIALIZED VIEW mv_workout_rankings;
    RETURN NULL; -- Result is ignored since this is an AFTER trigger
END;
$$ LANGUAGE plpgsql;
"""

# -- SQL for Dropping and Creating Triggers -------------------
# Instead of executing multiple DROP statements at once, split and execute them one by one.
drop_triggers_sql = [
    "DROP TRIGGER IF EXISTS trg_refresh_rowing_summary_on_workout ON workouts;",
    "DROP TRIGGER IF EXISTS trg_refresh_summary_on_equipment_update ON equipment_types;",
    "DROP TRIGGER IF EXISTS trg_refresh_workout_rankings_on_workout ON workouts;",
    "DROP TRIGGER IF EXISTS trg_refresh_workout_rankings_on_ranking_settings ON ranking_settings;"
]

create_triggers_sql = [
    """
    CREATE TRIGGER trg_refresh_rowing_summary_on_workout
    AFTER INSERT OR UPDATE OR DELETE ON workouts
    FOR EACH STATEMENT 
    EXECUTE FUNCTION refresh_rowing_summary_mvs();
    """,
    """
    CREATE TRIGGER trg_refresh_summary_on_equipment_update
    AFTER UPDATE ON equipment_types
    FOR EACH STATEMENT
    EXECUTE FUNCTION refresh_rowing_summary_mvs();
    """,
    """
    CREATE TRIGGER trg_refresh_workout_rankings_on_workout
    AFTER INSERT OR UPDATE OR DELETE ON workouts
    FOR EACH STATEMENT
    EXECUTE FUNCTION refresh_workout_rankings_mv();
    """,
    """
    CREATE TRIGGER trg_refresh_workout_rankings_on_ranking_settings
    AFTER INSERT OR UPDATE OR DELETE ON ranking_settings
    FOR EACH STATEMENT
    EXECUTE FUNCTION refresh_workout_rankings_mv();
    """
]




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

    CREATE MATERIALIZED VIEW mv_workout_rankings AS
    WITH base AS (
        SELECT
            rs.ranking_id,
            w.workout_id,
            w.workout_date,
            CASE WHEN rs.type = 'distance' THEN w.duration_seconds ELSE NULL END AS duration_seconds,
            CASE WHEN rs.type = 'time' THEN w.total_distance_meters ELSE NULL END AS total_distance_meters
        FROM
            ranking_settings rs
            JOIN workouts w ON (
                (rs.type = 'distance' AND w.total_distance_meters = rs.value)
                OR
                (rs.type = 'time' AND w.duration_seconds = rs.value)
            )
            JOIN equipment_types et ON w.equipment_type_id = et.equipment_type_id
        WHERE
            et.settings_include_in_totals = TRUE
    ),
    overall_ranks AS (
        SELECT
            ranking_id,
            workout_id,
            NULL::integer AS year,
            NULL::integer AS month,
            'overall'::text AS rank_type,
            ROW_NUMBER() OVER (
                PARTITION BY ranking_id
                ORDER BY
                    COALESCE(duration_seconds, 0) ASC,
                    COALESCE(total_distance_meters, 0) DESC
            ) AS rank
        FROM base
    ),
    yearly_ranks AS (
        SELECT
            ranking_id,
            workout_id,
            EXTRACT(YEAR FROM workout_date)::integer AS year,
            NULL::integer AS month,
            'year'::text AS rank_type,
            ROW_NUMBER() OVER (
                PARTITION BY ranking_id, EXTRACT(YEAR FROM workout_date)
                ORDER BY
                    COALESCE(duration_seconds, 0) ASC,
                    COALESCE(total_distance_meters, 0) DESC
            ) AS rank
        FROM base
    ),
    monthly_ranks AS (
        SELECT
            ranking_id,
            workout_id,
            EXTRACT(YEAR FROM workout_date)::integer AS year,
            EXTRACT(MONTH FROM workout_date)::integer AS month,
            'month'::text AS rank_type,
            ROW_NUMBER() OVER (
                PARTITION BY ranking_id, EXTRACT(YEAR FROM workout_date), EXTRACT(MONTH FROM workout_date)
                ORDER BY
                    COALESCE(duration_seconds, 0) ASC,
                    COALESCE(total_distance_meters, 0) DESC
            ) AS rank
        FROM base
    )
    SELECT
        ROW_NUMBER() OVER () AS id,
        ranking_id,
        workout_id,
        year,
        month,
        rank_type,
        rank
    FROM (
        SELECT * FROM overall_ranks
        UNION ALL
        SELECT * FROM yearly_ranks
        UNION ALL
        SELECT * FROM monthly_ranks
    ) all_ranks
    WITH DATA;
    """

# Default settings for UserSetting table
DEFAULT_USER_SETTINGS = {
    'per_page_workouts': '20',
    'per_page_summary_day': '14',
    'per_page_summary_week': '12',
    'per_page_summary_month': '12',
    'HR_Very_hard': '166',
    'HR_Hard': '147',
    'HR_Moderate': '129',
    'HR_Light': '111',
    'HR_Very_light': '0'
}

# Default ranking configurations
DEFAULT_RANKING_CONFIGURATIONS = [
    {'type': 'distance', 'value': 2000, 'label': '2000m'},
    {'type': 'distance', 'value': 5000, 'label': '5000m'},
    {'type': 'distance', 'value': 100, 'label': '100m'},
    {'type': 'distance', 'value': 500, 'label': '500m'},
    {'type': 'distance', 'value': 1000, 'label': '1000m'},
    {'type': 'distance', 'value': 6000, 'label': '6000m'},
    {'type': 'distance', 'value': 10000, 'label': '10000m'},
    {'type': 'distance', 'value': 21097, 'label': 'Half Marathon'},
    {'type': 'time', 'value': 60, 'label': '1:00'},      # 1 minute
    {'type': 'time', 'value': 240, 'label': '4:00'},     # 4 minutes
    {'type': 'time', 'value': 1800, 'label': '30:00'},   # 30 minutes
    {'type': 'time', 'value': 3600, 'label': '60:00'},   # 60 minutes # Corrected comment from 20 to 60 minutes
]

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

        # == Execute SQL Statements ============================================
        # Use a single transaction for all DDL operations.
        # This requires an app context for db.engine.
        with current_app.app_context():
            # Initial settings and configurations - first transaction
            with db.engine.connect() as connection:
                with connection.begin():
                    current_app.logger.info("Initializing default settings...")
                    default_settings = DEFAULT_USER_SETTINGS.copy()
                    default_settings['db_schema_ver'] = current_app.config.get('TARGET_DB_SCHEMA_VERSION', '0.0')
                    
                    for key, value in default_settings.items():
                        setting_exists = db.session.query(UserSetting).filter_by(key=key).first()
                        if not setting_exists:
                            new_setting = UserSetting(key=key, value=value)
                            db.session.add(new_setting)
                            current_app.logger.info(f"Initialized setting '{key}' to '{value}'.")
                        else:
                            current_app.logger.info(f"Setting '{key}' already exists with value '{setting_exists.value}'. No changes made by create_db_components for this key.")
                    
                    db.session.commit()
                    
                    current_app.logger.info("Initializing default ranking configurations...")
                    for config in DEFAULT_RANKING_CONFIGURATIONS:
                        ranking_exists = db.session.query(RankingSetting).filter_by(
                            type=config['type'], value=config['value'], label=config['label']).first()
                        
                        if not ranking_exists:
                            new_ranking = RankingSetting(
                                type=config['type'], value=config['value'], label=config['label'])
                            db.session.add(new_ranking)
                            current_app.logger.info(f"Initialized ranking configuration: {config['label']} ({config['type']}, {config['value']})")
                    
                    db.session.commit()

            # Materialized views - second transaction
            with db.engine.connect() as connection:
                with connection.begin():
                    current_app.logger.info("Creating materialized views...")
                    connection.execute(text(DROP_MVS_SQL))
                    connection.execute(text(create_mvs_sql))
                    
                    # Drop functions before recreating them
                    current_app.logger.info("Dropping existing functions...")
                    connection.execute(text(DROP_FUNCTIONS_SQL))
                    
                    current_app.logger.info("Creating database functions...")
                    connection.execute(text(create_function_sql))
                    connection.execute(text(create_function_ranking_sql))

            # Handle triggers differently - first create an engine with AUTOCOMMIT
            current_app.logger.info("Setting up AUTOCOMMIT engine for trigger operations")
            autocommit_engine = db.engine.execution_options(isolation_level="AUTOCOMMIT")

            # Drop triggers one by one with explicit error handling
            current_app.logger.info("Starting trigger drop operations...")
            for i, stmt in enumerate(drop_triggers_sql):
                try:
                    current_app.logger.info(f"Dropping trigger {i+1}/{len(drop_triggers_sql)}: Starting")
                    with autocommit_engine.connect() as connection:
                        # Keep statements extremely simple
                        current_app.logger.info(f"Executing drop: {stmt.strip()}")
                        connection.execute(text(stmt))
                    current_app.logger.info(f"Dropping trigger {i+1}/{len(drop_triggers_sql)}: Complete")
                except Exception as e:
                    current_app.logger.warning(f"Error dropping trigger: {e}")
                    # Continue with the next one regardless of errors
            
            # Force a small delay to ensure database has processed all operations
            import time
            current_app.logger.info("Waiting 2 seconds before creating triggers...")
            time.sleep(2)

            # Create triggers one by one, also with explicit error handling
            current_app.logger.info("Starting trigger create operations...")
            for i, stmt in enumerate(create_triggers_sql):
                try:
                    current_app.logger.info(f"Creating trigger {i+1}/{len(create_triggers_sql)}: Starting")
                    with autocommit_engine.connect() as connection:
                        # Keep statements extremely simple
                        current_app.logger.info(f"Executing create: {stmt.strip()}")
                        connection.execute(text(stmt))
                    current_app.logger.info(f"Creating trigger {i+1}/{len(create_triggers_sql)}: Complete")
                except Exception as e:
                    current_app.logger.error(f"Error creating trigger: {e}")
                    # Continue regardless of errors

            current_app.logger.info("Database components and default settings set up successfully!")
            return True

    except Exception as e:
        current_app.logger.error(f"Error setting up database components: {e}", exc_info=True)
        return False

# --------------------------------------------------------
# - Database Schema Update Function (Placeholder)
#---------------------------------------------------------
def update_db_schema(current_version, target_version):
    """Apply database schema migrations from current_version to target_version."""
    current_app.logger.info(f"Updating schema from {current_version} to {target_version}")
    
    # Import migration modules
    from db_migrations import v0_13_to_0_15, v0_15_to_0_16, v0_16_to_0_17, v0_17_to_0_18
    
    # Define available migrations
    migrations = {
        "0.13": {"target": "0.15", "upgrade": v0_13_to_0_15.upgrade},
        "0.15": {"target": "0.16", "upgrade": v0_15_to_0_16.upgrade},
        "0.16": {"target": "0.17", "upgrade": v0_16_to_0_17.upgrade},
        "0.17": {"target": "0.18", "upgrade": v0_17_to_0_18.upgrade}
    }
    
    effective_current_version = current_version
    
    while effective_current_version != target_version:
        if effective_current_version not in migrations:
            current_app.logger.warning(f"No migration path from {effective_current_version}")
            break
            
        migration = migrations[effective_current_version]
        if migration["target"] > target_version:
            # We've gone far enough
            break
            
        try:
            current_app.logger.info(f"Applying migration from {effective_current_version} to {migration['target']}")
            new_version = migration["upgrade"](db, current_app)
            effective_current_version = new_version
        except Exception as e:
            current_app.logger.error(f"Migration failed: {e}")
            return
    
    current_app.logger.info(f"Schema update complete. Current version: {effective_current_version}")