# ========================================================
# = settings.py - View for managing application settings
# ========================================================
from flask import render_template, request, flash, redirect, url_for, current_app
from models import db, UserSetting, EquipmentType # Added EquipmentType

# --------------------------------------------------------
# - Default Settings Values
#---------------------------------------------------------
# Define default values for settings if they are not found in the database.
DEFAULT_SETTINGS = {
    'per_page_workouts': '20',
    'per_page_summary_day': '14',
    'per_page_summary_week': '12',
    'per_page_summary_month': '12'
    # 'items_per_page' and 'preferred_theme' are removed as per new requirements
    # or managed elsewhere/differently.
}

# --------------------------------------------------------
# - Settings View Function
#---------------------------------------------------------
# Manages the display and updating of application settings.
# Handles both GET requests (to show the settings form) and
# POST requests (to save updated settings).
# This function will be registered directly with the app.
def show_settings():
    # == Handle POST Request (Save Settings) ============================================
    if request.method == 'POST':
        try:
            # -- Handle Pagination Settings -------------------
            settings_to_update = {
                'per_page_workouts': request.form.get('per_page_workouts'),
                'per_page_summary_day': request.form.get('per_page_summary_day'),
                'per_page_summary_week': request.form.get('per_page_summary_week'),
                'per_page_summary_month': request.form.get('per_page_summary_month')
            }

            for key, value_str in settings_to_update.items():
                if not value_str or not value_str.isdigit():
                    flash(f'{key.replace("_", " ").title()} must be a valid positive integer.', 'danger')
                    return redirect(url_for('settings'))
                
                value_int = int(value_str)
                if value_int <= 0:
                    flash(f'{key.replace("_", " ").title()} must be a positive integer.', 'danger')
                    return redirect(url_for('settings'))

                setting_obj = UserSetting.query.filter_by(key=key).first()
                if not setting_obj:
                    setting_obj = UserSetting(key=key)
                    db.session.add(setting_obj)
                setting_obj.value = str(value_int)
                current_app.logger.debug(f"Attempting to save {key}: {value_int}")

            # -- Handle EquipmentType 'settings_include_in_totals' -------------------
            all_equipment_types = EquipmentType.query.all()
            for equip_type in all_equipment_types:
                checkbox_name = f"equip_include_{equip_type.equipment_type_id}"
                # If checkbox_name is in request.form, it means it was checked.
                # HTML checkboxes only send a value if they are checked.
                is_included = checkbox_name in request.form
                if equip_type.settings_include_in_totals != is_included:
                    equip_type.settings_include_in_totals = is_included
                    current_app.logger.debug(f"Updating {equip_type.name} 'settings_include_in_totals' to {is_included}")
            
            # -- Commit Changes to Database -------------------
            db.session.commit()
            flash('Settings updated successfully!', 'success')
            current_app.logger.info("User settings updated successfully.")
        
        except ValueError as ve: # Specific error for type conversion
            db.session.rollback()
            flash(f'Invalid input value: {str(ve)}. Please check your entries.', 'danger')
            current_app.logger.warning(f"ValueError during settings update: {ve}", exc_info=True)
        except Exception as e: # General error handler
            db.session.rollback()
            flash(f'An error occurred while saving settings: {str(e)}', 'danger')
            current_app.logger.error(f"Exception during settings update: {e}", exc_info=True)
        
        return redirect(url_for('settings'))

    # == Handle GET Request (Display Settings) ============================================
    # Fetch current settings from the database or use defaults.
    settings_data = {}
    equipment_types_data = []
    try:
        for key, default_value in DEFAULT_SETTINGS.items():
            setting_obj = UserSetting.query.filter_by(key=key).first()
            if setting_obj and setting_obj.value and setting_obj.value.isdigit():
                settings_data[key] = int(setting_obj.value)
            else:
                settings_data[key] = int(default_value) # Use default if not found or invalid
                if setting_obj and (not setting_obj.value or not setting_obj.value.isdigit()):
                    current_app.logger.warning(f"Invalid '{key}' value '{setting_obj.value}' in DB, using default.")
                elif not setting_obj:
                     current_app.logger.info(f"Setting '{key}' not found in DB, using default '{default_value}'.")

        equipment_types_data = EquipmentType.query.order_by(EquipmentType.name).all()

    except Exception as e:
        current_app.logger.error(f"Error fetching settings for display: {e}", exc_info=True)
        flash("Could not retrieve current settings. Displaying defaults.", "warning")
        # Fallback to defaults in case of any error during fetch
        for key, default_value in DEFAULT_SETTINGS.items():
            settings_data[key] = int(default_value)
        equipment_types_data = [] # Ensure it's an empty list on error
    
    # == Render Template ============================================
    return render_template('settings.html', settings_data=settings_data, equipment_types=equipment_types_data)

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the settings view route with the Flask application.
def register_routes(app):
    app.add_url_rule('/settings/', endpoint='settings', view_func=show_settings, methods=['GET', 'POST'])
