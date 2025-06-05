def upgrade(db, current_app):
    from models import UserSetting
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
    
    return "0.15"  # Return the new version