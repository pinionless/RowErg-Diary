from sqlalchemy import text
from models import UserSetting, db

def upgrade(db_obj, current_app):
    """Upgrade database from version 0.21 to 0.22.
    
    Creates the mv_rolling_dist materialized view to track distance
    rolling averages across calendar days, ignoring empty days by dividing
    the total distance in the calendar window by the window size.
    """
    current_app.logger.info("Applying schema migration from 0.21 to 0.22 (Rolling Avg Dist).")
    try:
        with current_app.app_context():
            create_mv_sql = text("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS mv_rolling_dist AS
                WITH daily_totals AS (
                    SELECT
                        w.workout_date,
                        SUM(w.total_distance_meters) AS day_distance
                    FROM workouts w
                    JOIN equipment_types et ON w.equipment_type_id = et.equipment_type_id
                    WHERE
                        et.settings_include_in_totals = TRUE
                        AND w.total_distance_meters IS NOT NULL
                        AND w.total_distance_meters > 0
                    GROUP BY w.workout_date
                ),
                first_date AS (
                    SELECT MIN(workout_date) AS fd FROM daily_totals
                )
                SELECT
                    d.workout_date,
                    
                    -- All Time (cumulative unbounded)
                    SUM(d.day_distance) OVER (
                        ORDER BY d.workout_date 
                        ROWS UNBOUNDED PRECEDING
                    ) / (d.workout_date - f.fd + 1) AS avg_all_time,
                    
                    -- Last 365 Days
                    SUM(d.day_distance) OVER (
                        ORDER BY d.workout_date 
                        RANGE BETWEEN INTERVAL '364 days' PRECEDING AND CURRENT ROW
                    ) / LEAST(365, d.workout_date - f.fd + 1) AS avg_365_days,
                    
                    -- Last 180 Days
                    SUM(d.day_distance) OVER (
                        ORDER BY d.workout_date 
                        RANGE BETWEEN INTERVAL '179 days' PRECEDING AND CURRENT ROW
                    ) / LEAST(180, d.workout_date - f.fd + 1) AS avg_180_days,
                    
                    -- Last 90 Days
                    SUM(d.day_distance) OVER (
                        ORDER BY d.workout_date 
                        RANGE BETWEEN INTERVAL '89 days' PRECEDING AND CURRENT ROW
                    ) / LEAST(90, d.workout_date - f.fd + 1) AS avg_90_days,
                    
                    -- Last 30 Days
                    SUM(d.day_distance) OVER (
                        ORDER BY d.workout_date 
                        RANGE BETWEEN INTERVAL '29 days' PRECEDING AND CURRENT ROW
                    ) / LEAST(30, d.workout_date - f.fd + 1) AS avg_30_days,
                    
                    -- Last 7 Days
                    SUM(d.day_distance) OVER (
                        ORDER BY d.workout_date 
                        RANGE BETWEEN INTERVAL '6 days' PRECEDING AND CURRENT ROW
                    ) / LEAST(7, d.workout_date - f.fd + 1) AS avg_7_days
                
                FROM daily_totals d
                CROSS JOIN first_date f
                ORDER BY d.workout_date
                WITH DATA;
            """)

            with db_obj.engine.connect() as connection:
                with connection.begin():
                    connection.execute(create_mv_sql)
                    current_app.logger.info("Created mv_rolling_dist materialized view.")

            # Update trigger function
            update_trigger_sql = text("""
                CREATE OR REPLACE FUNCTION refresh_rowing_summary_mvs()
                RETURNS TRIGGER AS $$
                BEGIN
                    REFRESH MATERIALIZED VIEW mv_sum_totals;
                    REFRESH MATERIALIZED VIEW mv_year_totals;
                    REFRESH MATERIALIZED VIEW mv_month_totals;
                    REFRESH MATERIALIZED VIEW mv_week_totals;
                    REFRESH MATERIALIZED VIEW mv_day_totals;
                    REFRESH MATERIALIZED VIEW mv_rolling_avg;
                    REFRESH MATERIALIZED VIEW mv_rolling_dist;
                    RETURN NULL;
                END;
                $$ LANGUAGE plpgsql;
            """)

            with db_obj.engine.connect() as connection:
                with connection.begin():
                    connection.execute(update_trigger_sql)
                    current_app.logger.info("Updated refresh_rowing_summary_mvs trigger to include mv_rolling_dist.")

            # -- Update schema version -------------------
            migrated_to_version = "0.22"
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
        current_app.logger.error(f"Error migrating schema from 0.21 to 0.22: {e}", exc_info=True)
        return None
