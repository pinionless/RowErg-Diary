# ========================================================
# = seed_data.py - Generate fake workout data for development
# ========================================================
# Usage: flask shell < seed_data.py
#    or: python seed_data.py  (when run inside the app container)
# ========================================================
import random
import uuid
from datetime import date, timedelta
from app import create_app
from models import db, Workout, EquipmentType

# --------------------------------------------------------
# - Configuration
# --------------------------------------------------------
NUM_WORKOUTS = 300          # Total workouts to generate
START_DATE = date(2023, 1, 1)  # Earliest workout date
END_DATE = date(2026, 5, 17)   # Latest workout date

# Realistic workout profiles: (distance_m, approx_pace_range_sec_per_500m)
WORKOUT_PROFILES = [
    # Short intervals
    {'distance': 500,   'pace_min': 95,  'pace_max': 110, 'name': '500m Sprint'},
    {'distance': 1000,  'pace_min': 100, 'pace_max': 115, 'name': '1000m Piece'},
    # Standard distances
    {'distance': 2000,  'pace_min': 105, 'pace_max': 120, 'name': '2000m Test'},
    {'distance': 5000,  'pace_min': 110, 'pace_max': 125, 'name': '5000m Row'},
    {'distance': 6000,  'pace_min': 112, 'pace_max': 128, 'name': '6000m Steady State'},
    # Long rows
    {'distance': 10000, 'pace_min': 115, 'pace_max': 130, 'name': '10K Row'},
    {'distance': 21097, 'pace_min': 118, 'pace_max': 135, 'name': 'Half Marathon'},
    # Time-based (will be stored as distance achieved in X seconds)
    {'distance': None, 'time': 60,   'pace_min': 95,  'pace_max': 112, 'name': '1 Min Max'},
    {'distance': None, 'time': 240,  'pace_min': 105, 'pace_max': 120, 'name': '4 Min Piece'},
    {'distance': None, 'time': 1800, 'pace_min': 112, 'pace_max': 130, 'name': '30 Min Row'},
    {'distance': None, 'time': 3600, 'pace_min': 115, 'pace_max': 135, 'name': '60 Min Row'},
]

# --------------------------------------------------------
# - Helper Functions
# --------------------------------------------------------
def random_date_between(start, end):
    """Generate a random date between start and end."""
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))

def generate_workout(equipment_type_id, workout_date, profile, idx):
    """Generate a single realistic workout from a profile."""
    # Add slight fitness improvement over time (pace decreases ~0.5% per year)
    days_from_start = (workout_date - START_DATE).days
    fitness_factor = 1.0 - (days_from_start / (365 * 5)) * 0.03  # Very subtle improvement

    # Random pace within the profile range, adjusted by fitness
    base_pace = random.uniform(profile['pace_min'], profile['pace_max'])
    # Add daily variance (+/- 3 seconds)
    pace = base_pace * fitness_factor + random.uniform(-3, 3)
    pace = max(pace, 85)  # Floor at 1:25/500m

    if profile['distance'] is not None:
        # Distance-based workout
        distance = profile['distance']
        duration = (distance / 500.0) * pace
        target_desc = f"{distance}m"
    else:
        # Time-based workout
        duration = profile['time']
        distance = (duration / pace) * 500.0
        target_desc = f"{int(duration)}s"

    return Workout(
        cardio_log_id=f"seed-{uuid.uuid4().hex[:12]}",
        equipment_type_id=equipment_type_id,
        workout_name=profile['name'],
        workout_date=workout_date,
        target_description=target_desc,
        duration_seconds=round(duration, 1),
        total_distance_meters=round(distance, 0),
        average_split_seconds_500m=round(pace, 1),
        total_isoreps=None,
        notes=None,
        level=None,
    )

# --------------------------------------------------------
# - Main Seed Logic
# --------------------------------------------------------
def seed():
    app = create_app()
    with app.app_context():
        # Check if data already exists
        existing = Workout.query.count()
        if existing > 0:
            print(f"Database already has {existing} workouts. Skipping seed.")
            print("To re-seed, delete existing workouts first.")
            return

        # Ensure equipment types exist
        rower = EquipmentType.query.filter_by(name='Row Ergometer').first()
        if not rower:
            rower = EquipmentType(name='Row Ergometer', settings_include_in_totals=True)
            db.session.add(rower)
            db.session.flush()  # Get the ID
            print(f"Created equipment type: Row Ergometer (id={rower.equipment_type_id})")

        # Optionally add a bike erg (excluded from totals) for variety
        bike = EquipmentType.query.filter_by(name='Bike Ergometer').first()
        if not bike:
            bike = EquipmentType(name='Bike Ergometer', settings_include_in_totals=False)
            db.session.add(bike)
            db.session.flush()
            print(f"Created equipment type: Bike Ergometer (id={bike.equipment_type_id})")

        # Generate random dates, clustered to simulate real training patterns
        # (more workouts in some weeks, rest weeks, etc.)
        dates = []
        current = START_DATE
        while current <= END_DATE:
            # Simulate training blocks: 3-5 sessions per week for 3-4 weeks, then a lighter week
            block_weeks = random.randint(3, 5)
            for week in range(block_weeks):
                sessions_this_week = random.randint(3, 6)
                week_start = current + timedelta(weeks=week)
                for _ in range(sessions_this_week):
                    day_offset = random.randint(0, 6)
                    d = week_start + timedelta(days=day_offset)
                    if d <= END_DATE:
                        dates.append(d)
            # Light/rest week: 1-2 sessions
            rest_week_start = current + timedelta(weeks=block_weeks)
            for _ in range(random.randint(1, 2)):
                day_offset = random.randint(0, 6)
                d = rest_week_start + timedelta(days=day_offset)
                if d <= END_DATE:
                    dates.append(d)
            current = rest_week_start + timedelta(weeks=1)

        # Trim to desired count and sort
        random.shuffle(dates)
        dates = sorted(dates[:NUM_WORKOUTS])

        print(f"Generating {len(dates)} workouts from {dates[0]} to {dates[-1]}...")

        workouts = []
        for i, d in enumerate(dates):
            # 90% rower, 10% bike
            equip = rower if random.random() < 0.9 else bike
            profile = random.choice(WORKOUT_PROFILES)
            w = generate_workout(equip.equipment_type_id, d, profile, i)
            workouts.append(w)

        db.session.add_all(workouts)
        db.session.commit()

        print(f"Successfully seeded {len(workouts)} workouts!")
        print(f"  Date range: {dates[0]} → {dates[-1]}")
        print(f"  Rower workouts: {sum(1 for w in workouts if w.equipment_type_id == rower.equipment_type_id)}")
        print(f"  Bike workouts: {sum(1 for w in workouts if w.equipment_type_id == bike.equipment_type_id)}")

if __name__ == '__main__':
    seed()
