from sqlalchemy import text
from models import UserSetting, db

def upgrade(db_obj, current_app):
    """Upgrade database from version 0.18 to 0.19.
    
    Adds the mv_rolling_avg materialized view which precalculates
    cumulative distance-weighted rolling average pace per workout.
    """
    current_app.logger.info("Applying schema migration from 0.18 to 0.19 (Adding Rolling Avg MV).")
    try:
        with current_app.app_context():
            # -- Create the materialized view -------------------
            create_mv_sql = text("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS mv_rolling_avg AS
                SELECT
                    w.workout_id,
                    w.workout_date,
                    w.total_distance_meters,
                    w.duration_seconds,
                    w.average_split_seconds_500m,
                    SUM(w.duration_seconds) OVER (ORDER BY w.workout_date, w.workout_id) /
                        NULLIF(SUM(w.total_distance_meters) OVER (ORDER BY w.workout_date, w.workout_id), 0) * 500.0
                        AS rolling_avg_pace
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
                    connection.execute(create_mv_sql)
                    current_app.logger.info("Created mv_rolling_avg materialized view.")

            # -- Add trigger for auto-refresh -------------------
            # Update the summary refresh function to also refresh mv_rolling_avg
            update_function_sql = text("""
                CREATE OR REPLACE FUNCTION refresh_rowing_summary_mvs()
                RETURNS TRIGGER AS $$
                BEGIN
                    REFRESH MATERIALIZED VIEW mv_sum_totals;
                    REFRESH MATERIALIZED VIEW mv_year_totals;
                    REFRESH MATERIALIZED VIEW mv_month_totals;
                    REFRESH MATERIALIZED VIEW mv_week_totals;
                    REFRESH MATERIALIZED VIEW mv_day_totals;
                    REFRESH MATERIALIZED VIEW mv_rolling_avg;
                    RETURN NULL;
                END;
                $$ LANGUAGE plpgsql;
            """)

            with db_obj.engine.connect() as connection:
                with connection.begin():
                    connection.execute(update_function_sql)
                    current_app.logger.info("Updated refresh_rowing_summary_mvs() to include mv_rolling_avg.")

            # -- Update schema version -------------------
            migrated_to_version = "0.19"
            setting = db_obj.session.query(UserSetting).filter_by(key='db_schema_ver').first()
            if setting:
                setting.value = migrated_to_version
                current_app.logger.info(f"Updated db_schema_ver to {migrated_to_version}")
            else:
                new_setting = UserSetting(key='db_schema_ver', value=migrated_to_version)
                db_obj.session.add(new_setting)
                current_app.logger.info(f"Set initial db_schema_ver to {migrated_to_version}")

            db_obj.session.commit()
            current_app.logger.info(f"Database schema migration from 0.18 to {migrated_to_version} completed successfully.")
            return migrated_to_version

    except Exception as e:
        db_obj.session.rollback()
        current_app.logger.error(f"Error migrating schema from 0.18 to 0.19: {e}", exc_info=True)
        return None
