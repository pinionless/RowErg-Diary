from sqlalchemy import text
from models import UserSetting, db

def upgrade(db_obj, current_app):
    """Upgrade database from version 0.19 to 0.20.
    
    Re-creates the mv_rolling_avg materialized view to include all 6
    precalculated rolling average windows (All Time, 365, 180, 90, 30, 7 days)
    as separate columns.
    """
    current_app.logger.info("Applying schema migration from 0.19 to 0.20 (Upgrading Rolling Avg MV).")
    try:
        with current_app.app_context():
            # -- Drop and recreate the materialized view -------------------
            recreate_mv_sql = text("""
                DROP MATERIALIZED VIEW IF EXISTS mv_rolling_avg;
                
                CREATE MATERIALIZED VIEW mv_rolling_avg AS
                SELECT
                    w.workout_id,
                    w.workout_date,
                    w.total_distance_meters,
                    w.duration_seconds,
                    w.average_split_seconds_500m,
                    
                    -- All Time (cumulative unbounded)
                    SUM(w.duration_seconds) OVER (
                        ORDER BY w.workout_date, w.workout_id
                        ROWS UNBOUNDED PRECEDING
                    ) / NULLIF(SUM(w.total_distance_meters) OVER (
                        ORDER BY w.workout_date, w.workout_id
                        ROWS UNBOUNDED PRECEDING
                    ), 0) * 500.0 AS avg_all_time,
                    
                    -- Last 365 Days
                    SUM(w.duration_seconds) OVER (
                        ORDER BY w.workout_date
                        RANGE BETWEEN INTERVAL '365 days' PRECEDING AND CURRENT ROW
                    ) / NULLIF(SUM(w.total_distance_meters) OVER (
                        ORDER BY w.workout_date
                        RANGE BETWEEN INTERVAL '365 days' PRECEDING AND CURRENT ROW
                    ), 0) * 500.0 AS avg_365_days,
                    
                    -- Last 180 Days
                    SUM(w.duration_seconds) OVER (
                        ORDER BY w.workout_date
                        RANGE BETWEEN INTERVAL '180 days' PRECEDING AND CURRENT ROW
                    ) / NULLIF(SUM(w.total_distance_meters) OVER (
                        ORDER BY w.workout_date
                        RANGE BETWEEN INTERVAL '180 days' PRECEDING AND CURRENT ROW
                    ), 0) * 500.0 AS avg_180_days,
                    
                    -- Last 90 Days
                    SUM(w.duration_seconds) OVER (
                        ORDER BY w.workout_date
                        RANGE BETWEEN INTERVAL '90 days' PRECEDING AND CURRENT ROW
                    ) / NULLIF(SUM(w.total_distance_meters) OVER (
                        ORDER BY w.workout_date
                        RANGE BETWEEN INTERVAL '90 days' PRECEDING AND CURRENT ROW
                    ), 0) * 500.0 AS avg_90_days,
                    
                    -- Last 30 Days
                    SUM(w.duration_seconds) OVER (
                        ORDER BY w.workout_date
                        RANGE BETWEEN INTERVAL '30 days' PRECEDING AND CURRENT ROW
                    ) / NULLIF(SUM(w.total_distance_meters) OVER (
                        ORDER BY w.workout_date
                        RANGE BETWEEN INTERVAL '30 days' PRECEDING AND CURRENT ROW
                    ), 0) * 500.0 AS avg_30_days,
                    
                    -- Last 7 Days
                    SUM(w.duration_seconds) OVER (
                        ORDER BY w.workout_date
                        RANGE BETWEEN INTERVAL '7 days' PRECEDING AND CURRENT ROW
                    ) / NULLIF(SUM(w.total_distance_meters) OVER (
                        ORDER BY w.workout_date
                        RANGE BETWEEN INTERVAL '7 days' PRECEDING AND CURRENT ROW
                    ), 0) * 500.0 AS avg_7_days
                FROM
                    workouts w
                    JOIN equipment_types et ON w.equipment_type_id = et.equipment_type_id
                WHERE
                    et.settings_include_in_totals = TRUE
                    AND w.total_distance_meters IS NOT NULL
                    AND w.total_distance_meters > 0
                    AND w.duration_seconds IS NOT NULL
                    AND w.duration_seconds > 0
                    AND w.average_split_seconds_500m IS NOT NULL
                    AND w.average_split_seconds_500m > 0
                ORDER BY
                    w.workout_date, w.workout_id
                WITH DATA;
            """)

            with db_obj.engine.connect() as connection:
                with connection.begin():
                    connection.execute(recreate_mv_sql)
                    current_app.logger.info("Successfully upgraded mv_rolling_avg Materialized View.")

            # -- Update schema version -------------------
            migrated_to_version = "0.20"
            setting = db_obj.session.query(UserSetting).filter_by(key='db_schema_ver').first()
            if setting:
                setting.value = migrated_to_version
                current_app.logger.info(f"Updated db_schema_ver to {migrated_to_version}")
            else:
                new_setting = UserSetting(key='db_schema_ver', value=migrated_to_version)
                db_obj.session.add(new_setting)
                current_app.logger.info(f"Set initial db_schema_ver to {migrated_to_version}")

            db_obj.session.commit()
            current_app.logger.info(f"Database schema migration to {migrated_to_version} completed successfully.")
            return migrated_to_version

    except Exception as e:
        db_obj.session.rollback()
        current_app.logger.error(f"Error migrating schema from 0.19 to 0.20: {e}", exc_info=True)
        return None
