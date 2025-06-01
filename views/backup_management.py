import os
import json
import decimal
import datetime as dt # Alias datetime to avoid conflict with datetime type
from flask import Blueprint, current_app, flash, redirect, url_for, request, render_template, send_from_directory
from sqlalchemy import text # For executing raw SQL
from models import db, EquipmentType, Workout, MetricDescriptor, WorkoutSample, HeartRateSample, WorkoutHRZone, UserSetting
import shutil
import glob
import zipfile # Added for zipping

export_bp = Blueprint('backup_management', __name__, url_prefix='/backup') # Changed blueprint name

# EXPORT_FILENAME = "export.json" # This can also be removed if not used by restore later

MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
TEMP_BACKUP_SUBDIR = "backup/temp" # Used by create_export for parts
FINAL_BACKUP_DIR_NAME = "backup" # Directory where final .zip backups are stored
RESTORE_TEMP_EXTRACT_DIR = "backup/restore_temp" # Temp dir for extracting zip during restore

# New constants for chunked processing of large tables
CHUNK_SIZE = 5000  # Number of records to fetch per DB query for large tables
# Define which SQLAlchemy models are considered large
LARGE_TABLE_MODELS = [WorkoutSample, HeartRateSample, Workout] 

def model_to_dict_converter(instance):
    """Converts a SQLAlchemy model instance to a dictionary, handling specific types."""
    data = {}
    for column in instance.__table__.columns:
        value = getattr(instance, column.name)
        if isinstance(value, (dt.date, dt.datetime)): # Changed to dt.date and dt.datetime
            data[column.name] = value.isoformat()
        elif isinstance(value, decimal.Decimal):
            data[column.name] = str(value)  # Store Decimal as string to preserve precision
        else:
            data[column.name] = value
    return data

@export_bp.route('/create', methods=['GET'])
def create_export():
    temp_backup_dir = os.path.join(current_app.root_path, TEMP_BACKUP_SUBDIR)
    final_backup_dir = os.path.join(current_app.root_path, FINAL_BACKUP_DIR_NAME)
    
    try:
        # Ensure the temporary backup directory exists and is empty
        if os.path.exists(temp_backup_dir):
            shutil.rmtree(temp_backup_dir) # Remove existing temp dir and its contents
        os.makedirs(temp_backup_dir)
        current_app.logger.info(f"Created temporary backup directory: {temp_backup_dir}")

        # Ensure final backup directory exists
        if not os.path.exists(final_backup_dir):
            os.makedirs(final_backup_dir)
            current_app.logger.info(f"Created final backup directory: {final_backup_dir}")

        part_num = 1
        current_part_data_dict = {}
        part_files_created = []

        table_order = [
            ('user_settings', UserSetting),
            ('equipment_types', EquipmentType),
            ('metric_descriptors', MetricDescriptor),
            ('workouts', Workout), # Workout can be large
            ('heart_rate_samples', HeartRateSample), # Potentially large
            ('workout_samples', WorkoutSample), # Potentially very large
            ('workout_hr_zones', WorkoutHRZone),
        ]

        def write_data_to_part_file(p_num, data_dict, directory):
            filepath = os.path.join(directory, f"part{p_num}.json")
            with open(filepath, 'w') as f:
                json.dump(data_dict, f, indent=4)
            current_app.logger.info(f"Wrote part {p_num}.json with keys: {list(data_dict.keys())} to {filepath}")
            return filepath

        for table_key, ModelClass in table_order:
            current_app.logger.debug(f"Starting processing for table: {table_key}")

            if ModelClass in LARGE_TABLE_MODELS:
                current_app.logger.info(f"Processing large table '{table_key}' in chunks of {CHUNK_SIZE}...")
                page_num = 1
                while True:
                    pagination = ModelClass.query.paginate(page=page_num, per_page=CHUNK_SIZE, error_out=False)
                    raw_chunk_items = pagination.items
                    
                    if not raw_chunk_items:
                        current_app.logger.info(f"No more items for '{table_key}' on page {page_num}.")
                        break 

                    current_app.logger.debug(f"Fetched {len(raw_chunk_items)} items for '{table_key}' page {page_num}.")
                    serialized_items_to_add = [model_to_dict_converter(item) for item in raw_chunk_items]

                    # Construct what the next part would look like if this chunk is added, for size estimation.
                    # This avoids modifying current_part_data_dict prematurely.
                    potential_next_part_data = {}
                    # Copy data for other tables (shallow copy of lists is fine, they aren't modified here)
                    for k, v_list in current_part_data_dict.items():
                        if k != table_key:
                            potential_next_part_data[k] = v_list
                    
                    # Combine existing data for the current table_key with the new chunk
                    existing_data_for_current_table = current_part_data_dict.get(table_key, [])
                    combined_data_for_current_table = existing_data_for_current_table + serialized_items_to_add # Creates a new list
                    potential_next_part_data[table_key] = combined_data_for_current_table
                    
                    size_of_prospective_part = len(json.dumps(potential_next_part_data).encode('utf-8'))

                    if size_of_prospective_part > MAX_FILE_SIZE_BYTES:
                        # Current chunk causes an overflow if added to existing current_part_data_dict.
                        # 1. Write out current_part_data_dict AS IS (if it has data from previous tables/chunks).
                        #    This current_part_data_dict does NOT include the current serialized_items_to_add.
                        if current_part_data_dict: 
                            part_filepath = write_data_to_part_file(part_num, current_part_data_dict, temp_backup_dir)
                            part_files_created.append(part_filepath)
                            part_num += 1
                        
                        # 2. The new part starts with ONLY the current chunk.
                        current_part_data_dict = {table_key: serialized_items_to_add}
                        
                        # 3. Check if this single chunk itself is too large.
                        current_data_only_size = len(json.dumps(current_part_data_dict).encode('utf-8'))
                        if current_data_only_size > MAX_FILE_SIZE_BYTES:
                            # If the single chunk is too large, write it out immediately to its own part.
                            part_filepath = write_data_to_part_file(part_num, current_part_data_dict, temp_backup_dir)
                            part_files_created.append(part_filepath)
                            current_app.logger.warning(
                                f"Part {part_num} (single chunk from table '{table_key}') "
                                f"size {current_data_only_size / (1024*1024):.2f}MB "
                                f"exceeds max file size of {MAX_FILE_SIZE_MB}MB."
                            )
                            part_num += 1
                            current_part_data_dict = {} # This chunk has been written, so clear for the next.
                    else:
                        # It fits. Merge serialized_items_to_add into the actual current_part_data_dict.
                        if table_key not in current_part_data_dict:
                            current_part_data_dict[table_key] = []
                        current_part_data_dict[table_key].extend(serialized_items_to_add)

                    if not pagination.has_next:
                        break 
                    page_num += 1
                current_app.logger.info(f"Finished processing all chunks for large table '{table_key}'.")
            else: # Small table, process all at once
                current_app.logger.info(f"Processing small table '{table_key}' all at once...")
                all_items_raw = ModelClass.query.all()
                if not all_items_raw:
                    current_app.logger.info(f"Table '{table_key}' is empty. Skipping.")
                    continue
                
                serialized_items_to_add = [model_to_dict_converter(item) for item in all_items_raw]

                prospective_data_for_part = current_part_data_dict.copy()
                prospective_data_for_part[table_key] = serialized_items_to_add # Assign directly for small tables
                
                size_of_prospective_part = len(json.dumps(prospective_data_for_part).encode('utf-8'))

                if size_of_prospective_part > MAX_FILE_SIZE_BYTES:
                    if current_part_data_dict:
                        part_filepath = write_data_to_part_file(part_num, current_part_data_dict, temp_backup_dir)
                        part_files_created.append(part_filepath)
                        part_num += 1
                    
                    current_part_data_dict = {table_key: serialized_items_to_add}
                    current_data_only_size = len(json.dumps(current_part_data_dict).encode('utf-8'))
                    if current_data_only_size > MAX_FILE_SIZE_BYTES:
                        part_filepath = write_data_to_part_file(part_num, current_part_data_dict, temp_backup_dir)
                        part_files_created.append(part_filepath)
                        current_app.logger.warning(
                            f"Part {part_num} (containing only small table '{table_key}') "
                            f"size {current_data_only_size / (1024*1024):.2f}MB "
                            f"exceeds max file size of {MAX_FILE_SIZE_MB}MB."
                        )
                        part_num += 1
                        current_part_data_dict = {}
                else:
                    current_part_data_dict[table_key] = serialized_items_to_add # Assign directly
                current_app.logger.info(f"Finished processing small table '{table_key}'.")
        
        if current_part_data_dict:
            part_filepath = write_data_to_part_file(part_num, current_part_data_dict, temp_backup_dir)
            part_files_created.append(part_filepath)
            final_part_size = len(json.dumps(current_part_data_dict).encode('utf-8'))
            if final_part_size > MAX_FILE_SIZE_BYTES:
                 current_app.logger.warning(
                    f"Final part {part_num} "
                    f"size {final_part_size / (1024*1024):.2f}MB "
                    f"exceeds max file size of {MAX_FILE_SIZE_MB}MB."
                )
        
        if not part_files_created:
            flash('No data to backup.', 'info')
            current_app.logger.info("No data found to backup.")
            # Clean up empty temp_backup_dir if it was created
            if os.path.exists(temp_backup_dir):
                shutil.rmtree(temp_backup_dir)
            return redirect(url_for('backup_management.index')) # Changed redirect

        # Create Zip Archive
        zip_filename = dt.datetime.now().strftime("%Y%m%d_%H%M%S") + ".zip"
        zip_filepath = os.path.join(final_backup_dir, zip_filename)

        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zip_f:
            for part_file in part_files_created:
                zip_f.write(part_file, os.path.basename(part_file))
        
        current_app.logger.info(f"Successfully created zip archive: {zip_filepath}")

        # Cleanup temporary part files and directory
        if os.path.exists(temp_backup_dir):
            shutil.rmtree(temp_backup_dir)
            current_app.logger.info(f"Cleaned up temporary backup directory: {temp_backup_dir}")

        flash(f'Successfully created backup: {zip_filename}. You can find it in the list below or download it.', 'success') # Updated flash message
        current_app.logger.info(f"Data backup process complete. Archive: {zip_filepath}")

    except Exception as e:
        current_app.logger.error(f"Error creating multipart backup and zip: {e}", exc_info=True)
        flash(f'Error creating backup: {str(e)}', 'danger')
        # Attempt to clean up temp_backup_dir even on error, if it exists
        if os.path.exists(temp_backup_dir):
            try:
                shutil.rmtree(temp_backup_dir)
                current_app.logger.info(f"Cleaned up temporary backup directory after error: {temp_backup_dir}")
            except Exception as cleanup_e:
                current_app.logger.error(f"Error cleaning up temp directory after main error: {cleanup_e}", exc_info=True)
    
    return redirect(url_for('backup_management.index')) # Changed redirect

@export_bp.route('/restore', methods=['GET', 'POST'])
def restore_export():
    final_backup_dir = os.path.join(current_app.root_path, FINAL_BACKUP_DIR_NAME)
    restore_temp_dir = os.path.join(current_app.root_path, RESTORE_TEMP_EXTRACT_DIR)

    if request.method == 'GET':
        # GET request to /restore is now effectively handled by index showing the form.
        # This direct GET handler for /restore can be simplified or removed if all restore actions
        # are initiated from the /backup page. For now, redirect to the main backup page.
        flash("Please use the Backup Management page to select a backup for restoration.", "info")
        return redirect(url_for('backup_management.index')) # Changed to backup_management

    # POST request logic
    if not os.path.exists(final_backup_dir):
        flash(f"Backup directory '{final_backup_dir}' not found.", "danger")
        return redirect(url_for('backup_management.index')) # Changed to backup_management

    backup_files = sorted(glob.glob(os.path.join(final_backup_dir, "*.zip")))
    if not backup_files:
        flash("No backup files found to restore.", "warning")
        return redirect(url_for('backup_management.index')) # Changed to backup_management

    latest_backup_zip = os.path.join(final_backup_dir, backup_files[0])
    current_app.logger.info(f"Attempting to restore from latest backup: {latest_backup_zip}")

    # POST request logic from previous step, ensure selected_backup_filename is used
    selected_backup_filename = request.form.get('backup_filename')
    if not selected_backup_filename:
        flash("No backup file selected for restore.", "danger")
        return redirect(url_for('backup_management.index')) # Changed to backup_management

    backup_zip_path = os.path.join(final_backup_dir, selected_backup_filename)

    if not os.path.exists(backup_zip_path) or not selected_backup_filename.endswith(".zip"):
        flash(f"Selected backup file '{selected_backup_filename}' not found or is invalid.", "danger")
        return redirect(url_for('backup_management.index')) # Changed to backup_management
    
    current_app.logger.info(f"Attempting to restore from selected backup: {backup_zip_path}")

    try:
        # 1. Prepare temporary extraction directory
        if os.path.exists(restore_temp_dir):
            shutil.rmtree(restore_temp_dir)
        os.makedirs(restore_temp_dir)
        current_app.logger.info(f"Created temporary directory for restore: {restore_temp_dir}")

        # 2. Extract backup zip
        with zipfile.ZipFile(backup_zip_path, 'r') as zip_ref: # Use backup_zip_path
            zip_ref.extractall(restore_temp_dir)
        current_app.logger.info(f"Extracted '{selected_backup_filename}' to '{restore_temp_dir}'") # Log selected_backup_filename

        # 3. Clear existing data from database
        current_app.logger.info("Clearing existing database data...")
        # Order of deletion matters due to foreign key constraints.
        # Workout deletion cascades to WorkoutSample, HeartRateSample, WorkoutHRZone.
        Workout.query.delete()
        db.session.commit() 
        # Now delete other tables that might have dependencies cleared by Workout deletion or are independent.
        MetricDescriptor.query.delete()
        EquipmentType.query.delete()
        UserSetting.query.delete()
        db.session.commit()
        current_app.logger.info("Database cleared.")

        # 4. Restore data from part files
        part_files = sorted(glob.glob(os.path.join(restore_temp_dir, "part*.json")))
        if not part_files:
            raise Exception("No part files found in the backup archive.")

        # Define the order of table restoration (same as in create_export)
        table_order_map = {
            'user_settings': UserSetting,
            'equipment_types': EquipmentType,
            'metric_descriptors': MetricDescriptor,
            'workouts': Workout,
            'heart_rate_samples': HeartRateSample,
            'workout_samples': WorkoutSample,
            'workout_hr_zones': WorkoutHRZone,
        }
        
        # Table specific type converters
        def convert_item_data(table_key, item_data_dict):
            if table_key == 'workouts':
                if 'workout_date' in item_data_dict and item_data_dict['workout_date']:
                    item_data_dict['workout_date'] = dt.date.fromisoformat(item_data_dict['workout_date'])
                for field in ['duration_seconds', 'total_distance_meters', 'average_split_seconds_500m', 'total_isoreps']:
                    if item_data_dict.get(field) is not None:
                        item_data_dict[field] = decimal.Decimal(item_data_dict[field])
                if item_data_dict.get('level') is not None:
                    item_data_dict['level'] = float(item_data_dict['level'])
            elif table_key == 'workout_samples':
                if item_data_dict.get('value') is not None:
                    item_data_dict['value'] = decimal.Decimal(item_data_dict['value'])
            elif table_key == 'workout_hr_zones':
                for field in ['lower_bound_bpm', 'upper_bound_bpm', 'seconds_in_zone']:
                    if item_data_dict.get(field) is not None:
                        item_data_dict[field] = decimal.Decimal(item_data_dict[field])
            # Add other table-specific conversions if needed
            return item_data_dict


        for part_file_path in part_files:
            current_app.logger.info(f"Processing part file: {part_file_path}")
            with open(part_file_path, 'r') as f:
                part_data = json.load(f)
            
            for table_key, ModelClass in table_order_map.items():
                if table_key in part_data:
                    items_to_restore = []
                    for item_data_dict in part_data[table_key]:
                        converted_data = convert_item_data(table_key, item_data_dict.copy())
                        items_to_restore.append(ModelClass(**converted_data))
                    
                    if items_to_restore:
                        db.session.add_all(items_to_restore)
                        db.session.commit()
                        current_app.logger.info(f"Restored {len(items_to_restore)} items for table '{table_key}' from {os.path.basename(part_file_path)}")
        
        current_app.logger.info("Data insertion complete.")

        # 5. Reset primary key sequences (PostgreSQL specific)
        current_app.logger.info("Resetting primary key sequences for PostgreSQL...")
        # Table name and its primary key column name
        tables_with_sequences = {
            'equipment_types': 'equipment_type_id',
            'workouts': 'workout_id',
            'metric_descriptors': 'metric_descriptor_id',
            'workout_samples': 'sample_id',
            'heart_rate_samples': 'hr_sample_id',
            'workout_hr_zones': 'workout_hr_zone_id',
            'user_settings': 'id'
        }
        with db.engine.connect() as connection:
            with connection.begin(): # Start a transaction for sequence resets
                for table_name, pk_column_name in tables_with_sequences.items():
                    # SQL to get the current max ID and reset the sequence
                    # COALESCE handles empty tables by setting sequence to 1
                    # The third argument to setval ensures the sequence is marked as "called" if max_id was not null
                    sql = text(f"""
                        SELECT setval(
                            pg_get_serial_sequence('{table_name}', '{pk_column_name}'),
                            COALESCE((SELECT MAX({pk_column_name}) FROM {table_name}), 1),
                            (SELECT MAX({pk_column_name}) IS NOT NULL FROM {table_name})
                        );
                    """)
                    connection.execute(sql)
                    current_app.logger.info(f"Reset sequence for table '{table_name}'.")
            # Transaction for sequence resets is committed here
        current_app.logger.info("Primary key sequences reset.")

        flash(f"Successfully restored data from backup: {selected_backup_filename}", "success") # Use selected_backup_filename
        current_app.logger.info(f"Data restoration from '{selected_backup_filename}' complete.") # Use selected_backup_filename

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during restore from '{selected_backup_filename}': {e}", exc_info=True) # Use selected_backup_filename
        flash(f"Error restoring data: {str(e)}", "danger")
    finally:
        # 6. Cleanup temporary extraction directory
        if os.path.exists(restore_temp_dir):
            try:
                shutil.rmtree(restore_temp_dir)
                current_app.logger.info(f"Cleaned up temporary restore directory: {restore_temp_dir}")
            except Exception as cleanup_e:
                current_app.logger.error(f"Error cleaning up temp restore directory: {cleanup_e}", exc_info=True)
    
    return redirect(url_for('backup_management.index')) # Changed to backup_management


@export_bp.route('/', methods=['GET'])
def index():
    final_backup_dir = os.path.join(current_app.root_path, FINAL_BACKUP_DIR_NAME)
    available_backups = []
    if os.path.exists(final_backup_dir):
        # Sort by modification time, newest first
        try:
            backup_files_with_mtime = []
            for f_name in os.listdir(final_backup_dir):
                if f_name.endswith(".zip"):
                    full_path = os.path.join(final_backup_dir, f_name)
                    backup_files_with_mtime.append((f_name, os.path.getmtime(full_path)))
            
            # Sort by mtime (second element of tuple), descending
            backup_files_with_mtime.sort(key=lambda x: x[1], reverse=True)
            available_backups = [f_name for f_name, mtime in backup_files_with_mtime]
        except Exception as e:
            current_app.logger.error(f"Error listing backup files: {e}", exc_info=True)
            flash("Error listing backup files.", "danger")
            
    return render_template('backup_management.html', backups=available_backups)

@export_bp.route('/download/<filename>', methods=['GET'])
def download_backup(filename):
    backup_dir = os.path.join(current_app.root_path, FINAL_BACKUP_DIR_NAME)
    # Sanitize filename to prevent directory traversal
    if ".." in filename or filename.startswith("/"):
        flash("Invalid filename.", "danger")
        return redirect(url_for('backup_management.index'))
    
    file_path = os.path.join(backup_dir, filename)
    if not os.path.isfile(file_path):
        flash(f"Backup file '{filename}' not found.", "danger")
        return redirect(url_for('backup_management.index'))
        
    return send_from_directory(directory=backup_dir, path=filename, as_attachment=True)


def register_routes(app):
    app.register_blueprint(export_bp)
