# ========================================================
# = details.py - View for displaying detailed workout information
# ========================================================
from flask import render_template
from sqlalchemy.orm import joinedload
from models import db, Workout, MetricDescriptor, WorkoutSample, HeartRateSample # Added HeartRateSample
import json # Added json
# import math # No longer needed for chart data processing

# --------------------------------------------------------
# - Workout Details View Function
#---------------------------------------------------------
# Displays detailed information for a specific workout.
def details(workout_id):
    workout = Workout.query.options(
        joinedload(Workout.equipment_type_ref), # Eager load equipment type
    ).get_or_404(workout_id)

    charts_data_list = []
    
    time_categories = []
    
    workout_sample_times = db.session.query(WorkoutSample.time_offset_seconds).filter_by(workout_id=workout.workout_id).distinct().order_by(WorkoutSample.time_offset_seconds.asc()).all()

    if workout_sample_times:
        time_categories = sorted(list(set(t[0] for t in workout_sample_times)))

    

    if time_categories:
        pace_metric_descriptor = MetricDescriptor.query.filter_by(metric_name='RowingSplit').first()
        pace_metric_id = pace_metric_descriptor.metric_descriptor_id if pace_metric_descriptor else None
        pace_unit = pace_metric_descriptor.unit_of_measure if pace_metric_descriptor else None

        power_metric_descriptor = MetricDescriptor.query.filter_by(metric_name='Power').first()
        power_metric_id = power_metric_descriptor.metric_descriptor_id if power_metric_descriptor else None
        power_unit = power_metric_descriptor.unit_of_measure if power_metric_descriptor else None

        spm_metric_descriptor = MetricDescriptor.query.filter_by(metric_name='Spm').first()
        spm_metric_id = spm_metric_descriptor.metric_descriptor_id if spm_metric_descriptor else None
        spm_unit = spm_metric_descriptor.unit_of_measure if spm_metric_descriptor else None

        def calculate_average_from_series(series_data):
            if not series_data:
                return None
            valid_values = [d['y'] for d in series_data if d['y'] is not None]
            if not valid_values:
                return None
            try:
                return sum(valid_values) / len(valid_values)
            except TypeError: # In case y values are not numeric after all checks
                return None

        def get_series_values(current_workout_id, metric_id, metric_name_for_validation, categories_list):
            if not metric_id:
                return [{'x': t_offset, 'y': None} for t_offset in categories_list]
            
            samples_query = WorkoutSample.query.filter_by(
                workout_id=current_workout_id,
                metric_descriptor_id=metric_id
            ).order_by(WorkoutSample.time_offset_seconds.asc()).all()

            metric_samples_dict = {}
            for sample in samples_query:
                try:
                    value_float = float(sample.value)
                    # Apply specific validation rules
                    if metric_name_for_validation == 'RowingSplit':
                        metric_samples_dict[sample.time_offset_seconds] = value_float if value_float > 0 else None
                    elif metric_name_for_validation in ['Power', 'Spm']:
                        metric_samples_dict[sample.time_offset_seconds] = value_float if value_float > 0 else None
                    else: # Default for other metrics
                        metric_samples_dict[sample.time_offset_seconds] = value_float if value_float >= 0 else None
                except (ValueError, TypeError):
                    metric_samples_dict[sample.time_offset_seconds] = None
            
            # Create a list of {x, y} pairs
            series_list_of_dicts = []
            for t_offset in categories_list:
                series_list_of_dicts.append({'x': t_offset, 'y': metric_samples_dict.get(t_offset, None)})

            return series_list_of_dicts

        # Prepare Pace Chart Data
        if pace_metric_id: # Check if descriptor was found
            pace_series_values = get_series_values(workout.workout_id, pace_metric_id, 'RowingSplit', time_categories)
            if any(d['y'] is not None for d in pace_series_values): # Check if any y-value is not None
                
                pace_annotations_yaxis = []
                
                if workout.average_split_seconds_500m is not None:
                        avg_pace_seconds = float(workout.average_split_seconds_500m)
                        avg_pace_minutes = int(avg_pace_seconds // 60)
                        avg_pace_remainder_seconds = int(round(avg_pace_seconds % 60)) # Round seconds
                        # pace_unit_text = pace_unit if pace_unit else '/500m' # Unit removed from label
                        
                        pace_annotations_yaxis.append({
                            "y": avg_pace_seconds,
                            "borderColor": "#FF0000", # Red color
                            "borderWidth": 1,         # 1px width
                            "strokeDashArray": 0,     # Solid line
                            "label": {
                                "borderColor": "#FF0000",
                                "style": {
                                    "color": "#fff",
                                    "background": "#FF0000",
                                "fontSize": "13px",  # Reduced font size
                                "padding": {         # Reduced padding
                                    "left": 2,
                                    "right": 2,
                                    "top": 2,
                                    "bottom": 2
                                }
                            },
                                "text": f"{avg_pace_minutes}:{avg_pace_remainder_seconds:02d}", # Only value
                            }
                        })
                
                pace_annotations = {"yaxis": pace_annotations_yaxis}
                
                charts_data_list.append({
                    "element_id": "paceChart",
                    "title": "Pace (/500m)", 
                    "series_data_json": json.dumps(pace_series_values), 
                    "metric_key": "Pace",
                    "unit": pace_unit if pace_unit else "/500m",
                    "annotations_json": json.dumps(pace_annotations) # Add annotations here
                })
        
        # Prepare Power Chart Data
        if power_metric_id: # Check if descriptor was found
            power_series_values = get_series_values(workout.workout_id, power_metric_id, 'Power', time_categories)
            # print(f"--- Debug VIEW: Power series values (count: {len(power_series_values)}): {power_series_values[:10]}... ---")
            if any(d['y'] is not None for d in power_series_values): # Check if any y-value is not None
                power_annotations_yaxis = []
                avg_power = calculate_average_from_series(power_series_values)
                if avg_power is not None:
                    power_annotations_yaxis.append({
                        "y": avg_power,
                        "borderColor": "#FF0000", # Red color
                        "borderWidth": 1,         # 1px width
                        "strokeDashArray": 0,     # Solid line
                        "label": {
                            "borderColor": "#FF0000",
                            "style": {
                                "color": "#fff",
                                "background": "#FF0000",
                                "fontSize": "13px",  # Reduced font size
                                "padding": {         # Reduced padding
                                    "left": 2,
                                    "right": 2,
                                    "top": 2,
                                    "bottom": 2
                                }
                            },
                            "text": f"{avg_power:.0f}", # Only value
                        }
                    })
                    # print(f"--- Debug VIEW: Added average power annotation: {avg_power} ---")
                
                power_annotations_dict = {"yaxis": power_annotations_yaxis} if power_annotations_yaxis else None

                charts_data_list.append({
                    "element_id": "powerChart",
                    "title": f"Power ({power_unit if power_unit else 'Watts'})", 
                    "series_data_json": json.dumps(power_series_values), 
                    "metric_key": "Power",
                    "unit": power_unit if power_unit else "Watts",
                    "annotations_json": json.dumps(power_annotations_dict) if power_annotations_dict else None
                })


        # Prepare SPM Chart Data
        if spm_metric_id: # Check if descriptor was found
            spm_series_values = get_series_values(workout.workout_id, spm_metric_id, 'Spm', time_categories)
            # print(f"--- Debug VIEW: SPM series values (count: {len(spm_series_values)}): {spm_series_values[:10]}... ---")
            if any(d['y'] is not None for d in spm_series_values): # Check if any y-value is not None
                spm_annotations_yaxis = []
                avg_spm = calculate_average_from_series(spm_series_values)
                if avg_spm is not None:
                    spm_annotations_yaxis.append({
                        "y": avg_spm,
                        "borderColor": "#FF0000", # Red color
                        "borderWidth": 1,         # 1px width
                        "strokeDashArray": 0,     # Solid line
                        "label": {
                            "borderColor": "#FF0000",
                            "style": {
                                "color": "#fff",
                                "background": "#FF0000",
                                "fontSize": "13px",  # Reduced font size
                                "padding": {         # Reduced padding
                                    "left": 2,
                                    "right": 2,
                                    "top": 2,
                                    "bottom": 2
                                }
                            },
                            "text": f"{avg_spm:.0f}"
                        }
                    })
                    # print(f"--- Debug VIEW: Added average SPM annotation: {avg_spm} ---")

                spm_annotations_dict = {"yaxis": spm_annotations_yaxis} if spm_annotations_yaxis else None
                
                charts_data_list.append({
                    "element_id": "spmChart",
                    "title": f"Stroke Rate ({spm_unit if spm_unit else 'spm'})", 
                    "series_data_json": json.dumps(spm_series_values), 
                    "metric_key": "Cadence",
                    "unit": spm_unit if spm_unit else "spm",
                    "annotations_json": json.dumps(spm_annotations_dict) if spm_annotations_dict else None
                })




    return render_template(
        'details.html',
        workout=workout,
        charts_data_list=charts_data_list # Pass the new chart data
    )

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the workout details view route with the Flask application
def register_routes(app):
    app.add_url_rule('/details/<int:workout_id>', endpoint='details', view_func=details, methods=['GET'])