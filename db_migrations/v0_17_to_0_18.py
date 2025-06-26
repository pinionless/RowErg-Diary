from models import UserSetting, db

def upgrade(db_obj, current_app):
    """Upgrade database from version 0.17 to 0.18."""
    current_app.logger.info("Applying schema migration from 0.17 to 0.18 (Adding HR Zone Settings).")
    try:
        with current_app.app_context():
            # Add new HR settings
            hr_settings = {
                'HR_Very_hard': '166',
                'HR_Hard': '147',
                'HR_Moderate': '129',
                'HR_Light': '111',
                'HR_Very_light': '0'
            }

            for key, value in hr_settings.items():
                setting_exists = db_obj.session.query(UserSetting).filter_by(key=key).first()
                if not setting_exists:
                    new_setting = UserSetting(key=key, value=value)
                    db_obj.session.add(new_setting)
                    current_app.logger.info(f"Added new setting: {key} = {value}")

            # Update the schema version
            migrated_to_version = "0.18"
            setting = db_obj.session.query(UserSetting).filter_by(key='db_schema_ver').first()
            if setting:
                setting.value = migrated_to_version
                current_app.logger.info(f"Updated db_schema_ver to {migrated_to_version}")
            else:
                new_setting = UserSetting(key='db_schema_ver', value=migrated_to_version)
                db_obj.session.add(new_setting)
                current_app.logger.info(f"Set initial db_schema_ver to {migrated_to_version}")

            db_obj.session.commit()
            current_app.logger.info(f"Database schema migration from 0.17 to {migrated_to_version} completed successfully.")
            return migrated_to_version

    except Exception as e:
        db_obj.session.rollback()
        current_app.logger.error(f"Error migrating schema from 0.17 to 0.18: {e}", exc_info=True)
        return None
