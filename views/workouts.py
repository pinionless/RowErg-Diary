# views/workouts.py
from flask import render_template, redirect, url_for, current_app
from sqlalchemy.orm import joinedload
from models import Workout

def workouts(page_num=1):
    per_page_value = current_app.config.get('PER_PAGE', 10)

    workouts_pagination = Workout.query.options(
        joinedload(Workout.workout_summary_data)
    ).order_by(
        Workout.workout_date.desc(),
        Workout.workout_id.desc()
    ).paginate(page=page_num, per_page=per_page_value, error_out=False)

    workouts_display_data = []
    for workout in workouts_pagination.items:
        summary_values = {
            'Duration': 'N/A',
            'Distance': 'N/A',
            'Split': 'N/A'
        }
        for summary_item in workout.workout_summary_data:
            if summary_item.property_key == 'Duration':
                summary_values['Duration'] = summary_item.value_text
            elif summary_item.property_key == 'derivedTotalDistance':
                summary_values['Distance'] = summary_item.value_text
            elif summary_item.property_key == 'derivedSplit500m':
                summary_values['Split'] = summary_item.value_text
        
        workouts_display_data.append({
            'workout_obj': workout,
            'summary': summary_values
        })

    if not workouts_pagination.items and page_num > 1 and workouts_pagination.pages > 0 :
        return redirect(url_for('workouts_paginated', page_num=workouts_pagination.pages))
    elif not workouts_pagination.items and page_num > 1 and workouts_pagination.pages == 0:
        return redirect(url_for('workouts_paginated', page_num=1)) # or just workouts

    return render_template(
        'workouts.html',
        workouts_pagination=workouts_pagination,
        workouts_display_data=workouts_display_data
    )

def register_routes(app):
    # Need distinct endpoint names if the view function is reused or has different decorators for same path
    app.add_url_rule('/workouts/', endpoint='workouts', view_func=lambda: workouts(1), methods=['GET'])
    app.add_url_rule('/workouts/page/<int:page_num>', endpoint='workouts_paginated', view_func=workouts, methods=['GET'])