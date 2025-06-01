# ========================================================
# = settings.py - View for managing application settings
# ========================================================
from flask import render_template, request, flash, redirect, url_for, current_app
from models import db, UserSetting

# --------------------------------------------------------
# - Default Settings Values
#---------------------------------------------------------
# Define default values for settings if they are not found in the database.
DEFAULT_SETTINGS = {
    'items_per_page': 10,
    'preferred_theme': 'light'
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
            # -- Items per Page Setting -------------------
            items_per_page_val_str = request.form.get('items_per_page')
            if not items_per_page_val_str or not items_per_page_val_str.isdigit():
                flash('Items per page must be a valid positive integer.', 'danger')
                return redirect(url_for('settings'))
            
            items_per_page_val = int(items_per_page_val_str)
            if items_per_page_val <= 0:
                flash('Items per page must be a positive integer.', 'danger')
                return redirect(url_for('settings'))

            setting_items_per_page = UserSetting.query.filter_by(key='items_per_page').first()
            if not setting_items_per_page:
                setting_items_per_page = UserSetting(key='items_per_page')
                db.session.add(setting_items_per_page)
            setting_items_per_page.value = str(items_per_page_val)
            current_app.logger.debug(f"Attempting to save items_per_page: {items_per_page_val}")

            # -- Preferred Theme Setting -------------------
            preferred_theme_val = request.form.get('preferred_theme', DEFAULT_SETTINGS['preferred_theme'])
            if preferred_theme_val not in ['light', 'dark']: # Basic validation
                flash('Invalid theme selected. Please choose "light" or "dark".', 'danger')
                return redirect(url_for('settings'))

            setting_preferred_theme = UserSetting.query.filter_by(key='preferred_theme').first()
            if not setting_preferred_theme:
                setting_preferred_theme = UserSetting(key='preferred_theme')
                db.session.add(setting_preferred_theme)
            setting_preferred_theme.value = preferred_theme_val
            current_app.logger.debug(f"Attempting to save preferred_theme: {preferred_theme_val}")
            
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
    try:
        s_items_per_page = UserSetting.query.filter_by(key='items_per_page').first()
        if s_items_per_page and s_items_per_page.value and s_items_per_page.value.isdigit():
            settings_data['items_per_page'] = int(s_items_per_page.value)
        else:
            settings_data['items_per_page'] = DEFAULT_SETTINGS['items_per_page']
            if s_items_per_page and (not s_items_per_page.value or not s_items_per_page.value.isdigit()):
                current_app.logger.warning(f"Invalid 'items_per_page' value '{s_items_per_page.value}' in DB, using default.")
        
        s_preferred_theme = UserSetting.query.filter_by(key='preferred_theme').first()
        if s_preferred_theme and s_preferred_theme.value in ['light', 'dark']:
            settings_data['preferred_theme'] = s_preferred_theme.value
        else:
            settings_data['preferred_theme'] = DEFAULT_SETTINGS['preferred_theme']
            if s_preferred_theme and s_preferred_theme.value not in ['light', 'dark']:
                 current_app.logger.warning(f"Invalid 'preferred_theme' value '{s_preferred_theme.value}' in DB, using default.")

    except Exception as e:
        current_app.logger.error(f"Error fetching settings for display: {e}", exc_info=True)
        flash("Could not retrieve current settings. Displaying defaults.", "warning")
        # Fallback to defaults in case of any error during fetch
        settings_data['items_per_page'] = DEFAULT_SETTINGS['items_per_page']
        settings_data['preferred_theme'] = DEFAULT_SETTINGS['preferred_theme']
    
    # == Render Template ============================================
    return render_template('settings.html', settings_data=settings_data)

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the settings view route with the Flask application.
def register_routes(app):
    app.add_url_rule('/settings/', endpoint='settings', view_func=show_settings, methods=['GET', 'POST'])
