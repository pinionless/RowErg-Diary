from sqlalchemy import text
from models import UserSetting
from database_setup import DROP_MVS_SQL, _get_create_mvs_sql, create_function_sql

def upgrade(db, current_app):
    current_app.logger.info("Applying schema migration from 0.15 to 0.16 (Update Materialized Views and Triggers).")
    try:
        # Define the SQL for triggers
        final_drop_triggers_sql = """
        DROP TRIGGER IF EXISTS trg_refresh_rowing_summary_on_workout ON workouts;
        DROP TRIGGER IF EXISTS trg_refresh_summary_on_equipment_update ON equipment_types;
        """
        
        final_create_triggers_sql = """
        CREATE TRIGGER trg_refresh_rowing_summary_on_workout
        AFTER INSERT OR UPDATE OR DELETE ON workouts
        FOR EACH STATEMENT 
        EXECUTE FUNCTION refresh_rowing_summary_mvs();

        CREATE TRIGGER trg_refresh_summary_on_equipment_update
        AFTER UPDATE ON equipment_types
        FOR EACH STATEMENT
        EXECUTE FUNCTION refresh_rowing_summary_mvs();
        """
        
        # Execute DDL operations in individual statements to avoid transaction issues
        with db.engine.connect() as connection:
            # Drop and recreate views
            current_app.logger.info("Dropping existing materialized views...")
            connection.execute(text(DROP_MVS_SQL))
            
            current_app.logger.info("Creating new materialized views with updated definitions...")
            connection.execute(text(_get_create_mvs_sql()))
            
            current_app.logger.info("Creating function for refreshing materialized views...")
            connection.execute(text(create_function_sql))
            
            # Drop and recreate triggers in separate connections
            current_app.logger.info("Dropping existing triggers...")
            connection.execute(text(final_drop_triggers_sql))
            
            current_app.logger.info("Creating new triggers...")
            for statement in final_create_triggers_sql.strip().split(';'):
                if statement.strip():
                    try:
                        with db.engine.connect() as conn:
                            conn.execute(text(statement))
                    except Exception as e:
                        current_app.logger.warning(f"Error executing trigger statement: {e}")
        
        # Update the schema version in the database
        migrated_to_version = "0.16"
        setting = db.session.query(UserSetting).filter_by(key='db_schema_ver').first()
        if setting:
            setting.value = migrated_to_version
            db.session.add(setting) 
            current_app.logger.info(f"Updated 'db_schema_ver' to '{migrated_to_version}'.")
        else:
            current_app.logger.error(f"Could not find 'db_schema_ver' to update. Creating it.")
            new_schema_ver_setting = UserSetting(key='db_schema_ver', value=migrated_to_version)
            db.session.add(new_schema_ver_setting)

        db.session.commit() 
        current_app.logger.info(f"Database schema migration from 0.15 to {migrated_to_version} completed successfully.")
        return migrated_to_version

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error migrating schema from 0.15 to 0.16: {e}", exc_info=True)
        return None  # Explicit return None on error