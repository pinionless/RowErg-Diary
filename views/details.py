# ========================================================
# = details.py - View for displaying detailed workout information
# ========================================================
from flask import render_template
from sqlalchemy.orm import joinedload
from models import db, Workout, MetricDescriptor, WorkoutSample # Added MetricDescriptor, WorkoutSample
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
    print(f"--- Debug VIEW: Fetched workout: ID={workout.workout_id}, Name='{workout.workout_name}', Duration={workout.duration_seconds} ---")

    charts_data_list = []

    # == Chart Data Preparation: Time categories from "Duration" metric ==
    print(f"--- Debug VIEW: Starting chart data preparation for workout_id: {workout.workout_id} ---")
    
    time_categories = []
    duration_metric_descriptor = MetricDescriptor.query.filter_by(metric_name='Duration').first()

    if duration_metric_descriptor:
        print(f"--- Debug VIEW: Found 'Duration' MetricDescriptor ID: {duration_metric_descriptor.metric_descriptor_id} ---")
        duration_samples = WorkoutSample.query.filter_by(
            workout_id=workout.workout_id,
            metric_descriptor_id=duration_metric_descriptor.metric_descriptor_id
        ).order_by(WorkoutSample.time_offset_seconds.asc()).all()
        
        if duration_samples:
            # Use unique, sorted time_offset_seconds from "Duration" samples as categories
            time_categories = sorted(list(set(sample.time_offset_seconds for sample in duration_samples)))
            print(f"--- Debug VIEW: Generated time_categories from 'Duration' samples (count: {len(time_categories)}): {time_categories[:10]}...{time_categories[-5:] if len(time_categories) > 10 else ''} ---")
        else:
            print(f"--- Debug VIEW: No 'Duration' samples found for workout_id: {workout.workout_id}. No charts will be generated. ---")
    else:
        print(f"--- Debug VIEW: 'Duration' MetricDescriptor not found. No charts will be generated. ---")
    

    if time_categories: # Proceed only if time_categories are derived from "Duration" metric
        # Fetch other Metric Descriptor IDs and their units
        pace_metric_descriptor = MetricDescriptor.query.filter_by(metric_name='RowingSplit').first()
        pace_metric_id = pace_metric_descriptor.metric_descriptor_id if pace_metric_descriptor else None
        pace_unit = pace_metric_descriptor.unit_of_measure if pace_metric_descriptor else None
        print(f"--- Debug VIEW: Pace Metric ID (RowingSplit): {pace_metric_id}, Unit: {pace_unit} ---")

        power_metric_descriptor = MetricDescriptor.query.filter_by(metric_name='Power').first()
        power_metric_id = power_metric_descriptor.metric_descriptor_id if power_metric_descriptor else None
        power_unit = power_metric_descriptor.unit_of_measure if power_metric_descriptor else None
        print(f"--- Debug VIEW: Power Metric ID: {power_metric_id}, Unit: {power_unit} ---")

        spm_metric_descriptor = MetricDescriptor.query.filter_by(metric_name='Spm').first()
        spm_metric_id = spm_metric_descriptor.metric_descriptor_id if spm_metric_descriptor else None
        spm_unit = spm_metric_descriptor.unit_of_measure if spm_metric_descriptor else None
        print(f"--- Debug VIEW: SPM Metric ID: {spm_metric_id}, Unit: {spm_unit} ---")

        # Helper function to calculate average from series data (list of {'x': val, 'y': val})
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

        # Helper function to get series data (list of Y values) aligned with the given categories_list
        def get_series_values(current_workout_id, metric_id, metric_name_for_validation, categories_list):
            print(f"    --- Debug HELPER get_series_values: Called for metric_id={metric_id}, name='{metric_name_for_validation}' using categories_list (count: {len(categories_list)}) ---")
            if not metric_id:
                print(f"    --- Debug HELPER get_series_values: No metric_id for '{metric_name_for_validation}', returning list of Nones. ---")
                # For numeric x-axis, we need x,y pairs. If no metric_id, y will be None for each x from categories.
                return [{'x': t_offset, 'y': None} for t_offset in categories_list]
            
            samples_query = WorkoutSample.query.filter_by(
                workout_id=current_workout_id,
                metric_descriptor_id=metric_id
            ).order_by(WorkoutSample.time_offset_seconds.asc()).all()
            print(f"    --- Debug HELPER get_series_values: Fetched {len(samples_query)} samples for metric_id={metric_id}. First 5: {[(s.time_offset_seconds, s.value) for s in samples_query[:5]]} ---")

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
            
            print(f"    --- Debug HELPER get_series_values: Generated series_list_of_dicts for '{metric_name_for_validation}' (count: {len(series_list_of_dicts)}). Non-null y count: {sum(1 for d in series_list_of_dicts if d['y'] is not None)}. First 10: {series_list_of_dicts[:10]} ---")
            return series_list_of_dicts

        # Prepare Pace Chart Data
        if pace_metric_id: # Check if descriptor was found
            pace_series_values = get_series_values(workout.workout_id, pace_metric_id, 'RowingSplit', time_categories)
            print(f"--- Debug VIEW: Pace series values (count: {len(pace_series_values)}): {pace_series_values[:10]}... ---")
            if any(d['y'] is not None for d in pace_series_values): # Check if any y-value is not None
                
                pace_annotations_yaxis = []
                
                # Add 2:00 target line - DEVELOP LATER
                # pace_annotations_yaxis.append({
                #     "y": 120, # 2:00 pace in seconds
                #     "borderColor": "#FF0000", # Red color
                #     "borderWidth": 2,
                #     "strokeDashArray": 0, # Solid line
                #     "label": {
                #         "borderColor": "#FF0000",
                #         "style": {
                #             "color": "#fff",
                #             "background": "#FF0000",
                #             "fontSize": "12px",
                #             "padding": {
                #                 "left": 5,
                #                 "right": 5,
                #                 "top": 2,
                #                 "bottom": 2
                #             }
                #         },
                #         "text": "2:00 Target",
                #         "position": "right", 
                #         "offsetX": 5
                #     }
                # })

                # Add average pace line if available
                if workout.average_split_seconds_500m is not None:
                    try:
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
                        print(f"--- Debug VIEW: Added average pace annotation: {avg_pace_seconds}s ---")
                    except (ValueError, TypeError) as e:
                        print(f"--- Debug VIEW: Could not convert average_split_seconds_500m to float for annotation: {workout.average_split_seconds_500m}, Error: {e} ---")
                
                pace_annotations = {"yaxis": pace_annotations_yaxis}
                
                charts_data_list.append({
                    "element_id": "paceChart",
                    "title": "Pace (/500m)", 
                    "series_data_json": json.dumps(pace_series_values), 
                    "metric_key": "Pace",
                    "unit": pace_unit if pace_unit else "/500m",
                    "annotations_json": json.dumps(pace_annotations) # Add annotations here
                })
        else:
            print(f"--- Debug VIEW: Pace metric_id is None. Skipping Pace chart. ---")
        
        # Prepare Power Chart Data
        if power_metric_id: # Check if descriptor was found
            power_series_values = get_series_values(workout.workout_id, power_metric_id, 'Power', time_categories)
            print(f"--- Debug VIEW: Power series values (count: {len(power_series_values)}): {power_series_values[:10]}... ---")
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
                    print(f"--- Debug VIEW: Added average power annotation: {avg_power} ---")
                
                power_annotations_dict = {"yaxis": power_annotations_yaxis} if power_annotations_yaxis else None

                charts_data_list.append({
                    "element_id": "powerChart",
                    "title": f"Power ({power_unit if power_unit else 'Watts'})", 
                    "series_data_json": json.dumps(power_series_values), 
                    "metric_key": "Power",
                    "unit": power_unit if power_unit else "Watts",
                    "annotations_json": json.dumps(power_annotations_dict) if power_annotations_dict else None
                })
        else:
            print(f"--- Debug VIEW: Power metric_id is None. Skipping Power chart. ---")

        # Prepare SPM Chart Data
        if spm_metric_id: # Check if descriptor was found
            spm_series_values = get_series_values(workout.workout_id, spm_metric_id, 'Spm', time_categories)
            print(f"--- Debug VIEW: SPM series values (count: {len(spm_series_values)}): {spm_series_values[:10]}... ---")
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
                    print(f"--- Debug VIEW: Added average SPM annotation: {avg_spm} ---")

                spm_annotations_dict = {"yaxis": spm_annotations_yaxis} if spm_annotations_yaxis else None
                
                charts_data_list.append({
                    "element_id": "spmChart",
                    "title": f"Stroke Rate ({spm_unit if spm_unit else 'spm'})", 
                    "series_data_json": json.dumps(spm_series_values), 
                    "metric_key": "Cadence",
                    "unit": spm_unit if spm_unit else "spm",
                    "annotations_json": json.dumps(spm_annotations_dict) if spm_annotations_dict else None
                })
        else:
            print(f"--- Debug VIEW: SPM metric_id is None. Skipping SPM chart. ---")
    else:
        print(f"--- Debug VIEW: time_categories list is empty (likely 'Duration' metric/samples not found). No charts will be generated. ---")

    print(f"--- Debug VIEW: Final charts_data_list (count: {len(charts_data_list)}): ---")
    for i, chart_item in enumerate(charts_data_list):
        print(f"    Chart {i+1}: ID='{chart_item['element_id']}', Title='{chart_item['title']}', MetricKey='{chart_item['metric_key']}', Unit='{chart_item.get('unit')}', HasAnnotations: {'annotations_json' in chart_item}")



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