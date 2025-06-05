from sqlalchemy import text
from models import UserSetting, db # Added db import
from database_setup import (
    DROP_MVS_SQL, 
    _get_create_mvs_sql, 
    create_function_sql, 
    create_function_ranking_sql, # Added for ranking MV
    drop_triggers_sql,           # Use the list of individual drop statements
    create_triggers_sql          # Use the list of individual create statements
)

def upgrade(db_obj, current_app): # Renamed db to db_obj to avoid conflict with imported db
    current_app.logger.info("Applying schema migration from 0.15 to 0.16 (Update Materialized Views and Triggers).")
    try:
        # Block 1: Materialized Views and their refresh functions
        with db_obj.engine.connect() as connection:
            with connection.begin():
                current_app.logger.info("Dropping all existing materialized views...")
                connection.execute(text(DROP_MVS_SQL))
                
                current_app.logger.info("Creating/Recreating all materialized views with updated definitions...")
                connection.execute(text(_get_create_mvs_sql())) # This creates all MVs including ranking
                
                current_app.logger.info("Creating/Recreating function for refreshing summary materialized views...")
                connection.execute(text(create_function_sql))
                
                current_app.logger.info("Creating/Recreating function for refreshing ranking materialized view...")
                connection.execute(text(create_function_ranking_sql))
        
        # Block 2: Drop all triggers (using the imported list)
        current_app.logger.info("Dropping all existing triggers...")
        for stmt in drop_triggers_sql: # Iterate over the list of individual DROP statements
            with db_obj.engine.connect() as connection: # Use a new connection for each DDL
                try:
                    connection.execute(text(stmt))
                    # DDLs like DROP TRIGGER are often best in their own transaction/connection
                except Exception as e:
                    current_app.logger.warning(f"Error dropping trigger: {stmt.strip()} - {e}")

        # Block 3: Create all triggers (using the imported list)
        current_app.logger.info("Creating all new triggers...")
        for stmt in create_triggers_sql: # Iterate over the list of individual CREATE statements
            with db_obj.engine.connect() as connection: # Use a new connection for each DDL
                try:
                    connection.execute(text(stmt))
                except Exception as e:
                    # Important: Decide if a single trigger failure should halt the migration.
                    # For now, logging error and continuing. Consider re-raising to stop.
                    current_app.logger.error(f"Error creating trigger: {stmt.strip()} - {e}")
        
        # Update the schema version in the database
        migrated_to_version = "0.16"
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
        current_app.logger.info(f"Database schema migration from 0.15 to {migrated_to_version} completed successfully.")
        return migrated_to_version

    except Exception as e:
        db_obj.session.rollback()
        current_app.logger.error(f"Error migrating schema from 0.15 to 0.16: {e}", exc_info=True)
        return None