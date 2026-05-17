from sqlalchemy import text
from models import UserSetting, db

def upgrade(db_obj, current_app):
    """Upgrade database from version 0.20 to 0.21.
    
    Re-creates mv_rolling_avg to use per-workout-day aggregation
    with ROWS-based windows (counting workout days, not calendar days).
    """
    current_app.logger.info("Applying schema migration from 0.20 to 0.21 (Rolling Avg per workout day).")
    try:
        with current_app.app_context():
            recreate_mv_sql = text("""
                DROP MATERIALIZED VIEW IF EXISTS mv_rolling_avg;
                
                CREATE MATERIALIZED VIEW mv_rolling_avg AS
                WITH daily_totals AS (
                    SELECT
                        w.workout_date,
                        SUM(w.total_distance_meters) AS day_distance,
                        SUM(w.duration_seconds) AS day_duration
                    FROM workouts w
                    JOIN equipment_types et ON w.equipment_type_id = et.equipment_type_id
                    WHERE
                        et.settings_include_in_totals = TRUE
                        AND w.total_distance_meters IS NOT NULL
                        AND w.total_distance_meters > 0
                        AND w.duration_seconds IS NOT NULL
                        AND w.duration_seconds > 0
                        AND w.average_split_seconds_500m IS NOT NULL
                        AND w.average_split_seconds_500m > 0
                    GROUP BY w.workout_date
                )
                SELECT
                    workout_date,
                    day_distance,
                    day_duration,
                    day_duration / NULLIF(day_distance, 0) * 500.0 AS day_pace,
                    
                    SUM(day_duration) OVER (ORDER BY workout_date ROWS UNBOUNDED PRECEDING) /
                        NULLIF(SUM(day_distance) OVER (ORDER BY workout_date ROWS UNBOUNDED PRECEDING), 0) * 500.0
                        AS avg_all_time,
                    
                    SUM(day_duration) OVER (ORDER BY workout_date ROWS BETWEEN 364 PRECEDING AND CURRENT ROW) /
                        NULLIF(SUM(day_distance) OVER (ORDER BY workout_date ROWS BETWEEN 364 PRECEDING AND CURRENT ROW), 0) * 500.0
                        AS avg_365_days,
                    
                    SUM(day_duration) OVER (ORDER BY workout_date ROWS BETWEEN 179 PRECEDING AND CURRENT ROW) /
                        NULLIF(SUM(day_distance) OVER (ORDER BY workout_date ROWS BETWEEN 179 PRECEDING AND CURRENT ROW), 0) * 500.0
                        AS avg_180_days,
                    
                    SUM(day_duration) OVER (ORDER BY workout_date ROWS BETWEEN 89 PRECEDING AND CURRENT ROW) /
                        NULLIF(SUM(day_distance) OVER (ORDER BY workout_date ROWS BETWEEN 89 PRECEDING AND CURRENT ROW), 0) * 500.0
                        AS avg_90_days,
                    
                    SUM(day_duration) OVER (ORDER BY workout_date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) /
                        NULLIF(SUM(day_distance) OVER (ORDER BY workout_date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW), 0) * 500.0
                        AS avg_30_days,
                    
                    SUM(day_duration) OVER (ORDER BY workout_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) /
                        NULLIF(SUM(day_distance) OVER (ORDER BY workout_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 0) * 500.0
                        AS avg_7_days
                FROM daily_totals
                ORDER BY workout_date
                WITH DATA;
            """)

            with db_obj.engine.connect() as connection:
                with connection.begin():
                    connection.execute(recreate_mv_sql)
                    current_app.logger.info("Upgraded mv_rolling_avg to per-workout-day aggregation.")

            # -- Update schema version -------------------
            migrated_to_version = "0.21"
            setting = db_obj.session.query(UserSetting).filter_by(key='db_schema_ver').first()
            if setting:
                setting.value = migrated_to_version
            else:
                db_obj.session.add(UserSetting(key='db_schema_ver', value=migrated_to_version))
            db_obj.session.commit()
            current_app.logger.info(f"Database schema migration to {migrated_to_version} completed successfully.")
            return migrated_to_version

    except Exception as e:
        db_obj.session.rollback()
        current_app.logger.error(f"Error migrating schema from 0.20 to 0.21: {e}", exc_info=True)
        return None
