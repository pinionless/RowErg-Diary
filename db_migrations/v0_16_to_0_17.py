from sqlalchemy import text
from models import UserSetting, RankingSetting, db
from database_setup import (
    DEFAULT_RANKING_CONFIGURATIONS,
    create_function_ranking_sql,
    create_function_sql,  # <-- Add this import for the summary function
    drop_triggers_sql,
    create_triggers_sql
)

def upgrade(db_obj, current_app):
    """Upgrade database from version 0.16 to 0.17."""
    current_app.logger.info("Applying schema migration from 0.16 to 0.17 (Adding Ranking Settings).")
    try:
        # Create the ranking_settings table if it doesn't exist
        current_app.logger.info("Ensuring ranking_settings table exists...")
        with current_app.app_context():
            db_obj.create_all()
        
        # Insert default ranking configurations
        current_app.logger.info("Inserting default ranking configurations...")
        for config in DEFAULT_RANKING_CONFIGURATIONS:
            ranking_exists = db_obj.session.query(RankingSetting).filter_by(
                type=config['type'],
                value=config['value'],
                label=config['label']
            ).first()
            
            if not ranking_exists:
                new_ranking = RankingSetting(
                    type=config['type'],
                    value=config['value'],
                    label=config['label']
                )
                db_obj.session.add(new_ranking)
                current_app.logger.info(f"Added default ranking configuration: {config['label']}")
        
        # Create ranking materialized view in a separate transaction
        current_app.logger.info("Creating ranking materialized view...")
        ranking_mv_sql = """
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
        
        # Execute view creation and function in separate connections
        with db_obj.engine.connect() as connection:
            with connection.begin():
                # Create both functions needed by triggers
                current_app.logger.info("Creating summary refresh function...")
                connection.execute(text(create_function_sql))  # <-- Add this to create the summary function
                
                current_app.logger.info("Creating ranking refresh function...")
                connection.execute(text(create_function_ranking_sql))
        
        with db_obj.engine.connect() as connection:
            with connection.begin():
                # Drop and recreate materialized view
                connection.execute(text("DROP MATERIALIZED VIEW IF EXISTS mv_workout_rankings;"))
                connection.execute(text(ranking_mv_sql))
        
        # Force a commit to ensure all previous operations are completed
        db_obj.session.commit()
        
        # Handle triggers differently - first create an engine with AUTOCOMMIT
        current_app.logger.info("Setting up AUTOCOMMIT engine for trigger operations")
        autocommit_engine = db_obj.engine.execution_options(isolation_level="AUTOCOMMIT")
        
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
        
        # Update the schema version in the database
        migrated_to_version = "0.17"
        setting = db_obj.session.query(UserSetting).filter_by(key='db_schema_ver').first()
        if setting:
            setting.value = migrated_to_version
            db_obj.session.add(setting)
            current_app.logger.info(f"Updated 'db_schema_ver' to '{migrated_to_version}'.")
        else:
            current_app.logger.error(f"Could not find 'db_schema_ver' to update. Creating it.")
            new_schema_ver_setting = UserSetting(key='db_schema_ver', value=migrated_to_version)
            db_obj.session.add(new_schema_ver_setting)

        db_obj.session.commit()
        current_app.logger.info(f"Database schema migration from 0.16 to {migrated_to_version} completed successfully.")
        return migrated_to_version

    except Exception as e:
        db_obj.session.rollback()
        current_app.logger.error(f"Error migrating schema from 0.16 to 0.17: {e}", exc_info=True)
        return None
