# views/home.py
from flask import render_template
from sqlalchemy.orm import joinedload
from models import Workout

def home():
    latest_five_workouts = Workout.query.options(
        joinedload(Workout.workout_summary_data)  # Eager load summary data
    ).order_by(
        Workout.workout_date.desc(),  # Order by date descending (newest first)
        Workout.workout_id.desc()     # Secondary sort by ID descending (if dates are same)
    ).limit(5).all()

    workouts_display_data = []
    # Iterate over the list of the 5 (or fewer, if less than 5 exist) Workout objects
    for workout_item in latest_five_workouts:
        summary_values = {
            'Duration': 'N/A',
            'Distance': 'N/A',
            'Split': 'N/A'
        }
        # Access workout_summary_data directly from the loaded workout_item
        for summary_item_detail in workout_item.workout_summary_data:
            if summary_item_detail.property_key == 'Duration':
                summary_values['Duration'] = summary_item_detail.value_text
            elif summary_item_detail.property_key == 'derivedTotalDistance':
                summary_values['Distance'] = summary_item_detail.value_text
            elif summary_item_detail.property_key == 'derivedSplit500m':
                summary_values['Split'] = summary_item_detail.value_text
        
        workouts_display_data.append({
            'workout_obj': workout_item,  # This is the actual Workout model instance
            'name': workout_item.workout_name,  # <<< ADDED THIS LINE
            'summary': summary_values
        })

    return render_template('index.html',
        workouts_display_data=workouts_display_data
    )

def register_routes(app):
    app.add_url_rule('/', view_func=home, methods=['GET'])