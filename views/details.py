# ========================================================
# = details.py - View for displaying detailed workout information
# ========================================================
from flask import render_template, current_app
from sqlalchemy.orm import joinedload
from models import db, Workout, MetricDescriptor, WorkoutSample, HeartRateSample, RankingSetting, UserSetting
from sqlalchemy import text
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

    # Get ranking information for this workout
    ranking_data = {}
    
    # Query for rankings from the materialized view
    ranking_query = text("""
        SELECT 
            r.ranking_id, r.rank, r.rank_type, r.year, r.month,
            rs.type, rs.value, rs.label
        FROM 
            mv_workout_rankings r
            JOIN ranking_settings rs ON r.ranking_id = rs.ranking_id
        WHERE 
            r.workout_id = :workout_id
        ORDER BY rs.type, rs.value
    """)
    
    try:
        ranking_results = db.session.execute(ranking_query, {'workout_id': workout_id}).fetchall()
        
        # Format ranking results
        for row in ranking_results:
            ranking_key = f"{row.type}-{row.value}"
            if ranking_key not in ranking_data:
                ranking_data[ranking_key] = {
                    'label': row.label,
                    'type': row.type,
                    'value': row.value,
                    'ranks': {}
                }
            
            # Add rank by type
            if row.rank_type == 'overall':
                ranking_data[ranking_key]['ranks']['overall'] = row.rank
            elif row.rank_type == 'year' and row.year:
                ranking_data[ranking_key]['ranks'][f'year_{row.year}'] = {
                    'year': row.year,
                    'rank': row.rank
                }
            elif row.rank_type == 'month' and row.year and row.month:
                ranking_data[ranking_key]['ranks'][f'month_{row.year}_{row.month}'] = {
                    'year': row.year,
                    'month': row.month,
                    'rank': row.rank
                }
                
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error fetching workout rankings: {e}")
        ranking_data = {}

    charts_data_list = []
    
    time_categories = []
    
    workout_sample_times = db.session.query(WorkoutSample.time_offset_seconds).filter_by(workout_id=workout.workout_id).distinct().order_by(WorkoutSample.time_offset_seconds.asc()).all()

    if workout_sample_times:
        time_categories = sorted(list(set(t[0] for t in workout_sample_times)))
        # Ensure time 0 is included in categories if data doesn't start at 0
        if time_categories and min(time_categories) > 0:
            time_categories = [0] + time_categories

    

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
            
            # Create a list of {x, y} pairs, ensuring we start at time 0
            series_list_of_dicts = []
            # Always add a point at time 0 if not present
            if 0 not in metric_samples_dict and categories_list and min(categories_list) > 0:
                series_list_of_dicts.append({'x': 0, 'y': None})
            
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

    # Prepare Heart Rate Chart Data (independent of time_categories since HR data may have different timing)
    hr_samples_query = HeartRateSample.query.filter_by(
        workout_id=workout.workout_id
    ).order_by(HeartRateSample.time_offset_seconds.asc()).all()
    
    if hr_samples_query:
        hr_series_values = []
        
        # Check if heart rate data starts after time 0, if so add a null point at time 0
        first_hr_time = hr_samples_query[0].time_offset_seconds if hr_samples_query else None
        if first_hr_time is not None and first_hr_time > 0:
            hr_series_values.append({'x': 0, 'y': None})
        
        for sample in hr_samples_query:
            if sample.heart_rate_bpm is not None and sample.heart_rate_bpm > 0:
                hr_series_values.append({
                    'x': sample.time_offset_seconds,
                    'y': int(sample.heart_rate_bpm)
                })
        
        if hr_series_values:  # Check if we have valid heart rate data
            hr_annotations_yaxis = []
            
            # Fetch HR Zone settings
            hr_zone_settings = db.session.query(UserSetting).filter(UserSetting.key.like('HR_%')).all()
            hr_zones = {setting.key: int(setting.value) for setting in hr_zone_settings if setting.value.isdigit()}
            print(f"--- Debug HR Zones from DB: {hr_zones} ---")

            if hr_zones:
                zone_colors = {
                    'HR_Very_light': 'rgb(173, 216, 230)', # Light Blue
                    'HR_Light':      'rgb(144, 238, 144)', # Light Green
                    'HR_Moderate':   'rgb(255, 255, 0)',   # Yellow
                    'HR_Hard':       'rgb(255, 165, 0)',   # Orange
                    'HR_Very_hard':  'rgb(255, 99, 71)'    # Tomato Red
                }

                # Define the zones in a canonical order
                zone_definitions = [
                    {'key': 'HR_Very_light', 'name': 'Very Light'},
                    {'key': 'HR_Light',      'name': 'Light'},
                    {'key': 'HR_Moderate',   'name': 'Moderate'},
                    {'key': 'HR_Hard',       'name': 'Hard'},
                    {'key': 'HR_Very_hard',  'name': 'Very Hard'}
                ]

                for i, zone_def in enumerate(zone_definitions):
                    zone_key = zone_def['key']
                    
                    if zone_key not in hr_zones:
                        continue

                    y_start = hr_zones[zone_key]
                    y_end = None
                    
                    # Find the start of the next zone to define the end of the current one
                    if i + 1 < len(zone_definitions):
                        next_zone_key = zone_definitions[i+1]['key']
                        if next_zone_key in hr_zones:
                            y_end = hr_zones[next_zone_key]

                    # Create label
                    if y_end is not None:
                        # The end of the zone is one less than the start of the next zone
                        label_text = f"{zone_def['name']} ({y_start} - {y_end - 1})"
                    else:
                        # This is the last zone (Very Hard)
                        label_text = f"{zone_def['name']} ({y_start}+)"
                        if zone_key == 'HR_Very_hard':
                            y_end = 300

                    print(f"--- Debug Zone: key={zone_key}, y_start={y_start}, y_end={y_end}, label='{label_text}' ---")

                    hr_annotations_yaxis.append({
                        "y": y_start,
                        "y2": y_end,
                        "borderColor": "#ddd",
                        "fillColor": zone_colors.get(zone_key, 'rgb(220, 220, 220)'),
                        "opacity": 0.35,
                    })

            # Calculate average heart rate (excluding None values)
            valid_hr_values = [point['y'] for point in hr_series_values if point['y'] is not None]
            if valid_hr_values:
                avg_hr = sum(valid_hr_values) / len(valid_hr_values)
                if avg_hr > 0:
                    hr_annotations_yaxis.append({
                        "y": avg_hr,
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
                            "text": f"{avg_hr:.0f}", # Only value
                        }
                    })
            
            hr_annotations_dict = {"yaxis": hr_annotations_yaxis} if hr_annotations_yaxis else None
            
            charts_data_list.append({
                "element_id": "heartRateChart",
                "title": "Heart Rate (bpm)", 
                "series_data_json": json.dumps(hr_series_values), 
                "metric_key": "HeartRate",
                "unit": "bpm",
                "annotations_json": json.dumps(hr_annotations_dict) if hr_annotations_dict else None
            })

    # Calculate time spent in each heart rate zone
    hr_zone_table_data = []
    if hr_series_values and hr_zones and 'zone_definitions' in locals():
        # Build zone ranges first
        zone_ranges = []
        for i, zone_def in enumerate(zone_definitions):
            zone_key = zone_def['key']
            if zone_key in hr_zones:
                y_start = hr_zones[zone_key]
                y_end = float('inf')
                
                # Find the start of the next zone to define the end of the current one
                next_zone_start = None
                if i + 1 < len(zone_definitions):
                    next_zone_key = zone_definitions[i+1]['key']
                    if next_zone_key in hr_zones:
                        next_zone_start = hr_zones[next_zone_key]
                
                if next_zone_start is not None:
                    y_end = next_zone_start
                
                zone_ranges.append({'key': zone_key, 'name': zone_def['name'], 'start': y_start, 'end': y_end, 'time': 0})

        # Calculate time in each zone
        if len(hr_series_values) > 1:
            for i in range(1, len(hr_series_values)):
                prev_point = hr_series_values[i-1]
                curr_point = hr_series_values[i]

                if prev_point['y'] is None or curr_point['x'] is None or prev_point['x'] is None:
                    continue

                duration = curr_point['x'] - prev_point['x']
                hr = prev_point['y']

                for zone in zone_ranges:
                    if zone['start'] <= hr < zone['end']:
                        zone['time'] += duration
                        break
        
        total_hr_duration = sum(zone['time'] for zone in zone_ranges)

        # Prepare data for the template
        for zone in zone_ranges:
            percentage = (zone['time'] / total_hr_duration) * 100 if total_hr_duration > 0 else 0
            
            range_str = f"{zone['start']} - {zone['end'] - 1}" if zone['end'] != float('inf') else f"{zone['start']}+"

            hr_zone_table_data.append({
                'name': zone['name'],
                'range': range_str,
                'time': zone['time'],
                'percentage': f"{percentage:.1f}%",
                'color': zone_colors.get(zone['key'], 'rgb(220, 220, 220)')
            })

    return render_template(
        'details.html',
        workout=workout,
        charts_data_list=charts_data_list,
        ranking_data=ranking_data,
        hr_zone_table_data=hr_zone_table_data
    )

# --------------------------------------------------------
# - Route Registration
#---------------------------------------------------------
# Registers the workout details view route with the Flask application
def register_routes(app):
    app.add_url_rule('/details/<int:workout_id>', endpoint='details', view_func=details, methods=['GET'])
