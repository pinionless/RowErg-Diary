def upgrade(db, current_app):
    current_app.logger.info("Applying schema migration from 0.16 to 0.17 (Adding Ranking Settings).")
    try:
        # Create the ranking_settings table if it doesn't exist
        # This uses SQLAlchemy's create_all which is safe to run even if tables exist
        current_app.logger.info("Ensuring ranking_settings table exists...")
        with current_app.app_context():
            db.create_all()
        
        # Insert default ranking configurations
        current_app.logger.info("Inserting default ranking configurations...")
        for config in DEFAULT_RANKING_CONFIGURATIONS:
            # Check if this configuration already exists
            ranking_exists = db.session.query(RankingSetting).filter_by(
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
                db.session.add(new_ranking)
                current_app.logger.info(f"Added default ranking configuration: {config['label']} ({config['type']}, {config['value']})")
        
        # Create the materialized view, function and triggers for rankings
        current_app.logger.info("Creating ranking materialized view and triggers...")
        
        # Get the SQL for the materialized view that includes rankings
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
        
        # Execute the SQL in separate transactions to avoid issues
        with db.engine.connect() as connection:
            # Create the refresh function for rankings
            connection.execute(text(create_function_ranking_sql))
            
            # Drop and recreate materialized view
            connection.execute(text("DROP MATERIALIZED VIEW IF EXISTS mv_workout_rankings;"))
            connection.execute(text(ranking_mv_sql))
            
            # Create triggers for workouts table
            for stmt in drop_triggers_sql:
                try:
                    connection.execute(text(stmt))
                except Exception as e:
                    current_app.logger.warning(f"Error dropping trigger: {e}")
            
            # Create triggers one by one in separate connections
            for stmt in create_triggers_sql:
                try:
                    with db.engine.connect() as conn_trigger:
                        conn_trigger.execute(text(stmt))
                except Exception as e:
                    current_app.logger.error(f"Error creating trigger: {e}")
        
        # Update the schema version
        migrated_to_version = "0.17"
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
        current_app.logger.info(f"Database schema migration from 0.16 to {migrated_to_version} completed successfully.")
        effective_current_version = migrated_to_version
        applied_migration_in_iteration = True
        return migrated_to_version

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error migrating schema from 0.16 to 0.17: {e}", exc_info=True)
    return None  # Explicit return None on error
