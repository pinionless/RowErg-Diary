# ========================================================
# = models.py - Database schema definition
# ========================================================
from flask_sqlalchemy import SQLAlchemy

# --------------------------------------------------------
# - SQLAlchemy Database Instance
#---------------------------------------------------------
# Global SQLAlchemy database instance
db = SQLAlchemy()

# --------------------------------------------------------
# - EquipmentType Model
#---------------------------------------------------------
# Defines the types of workout equipment
class EquipmentType(db.Model):
    __tablename__ = 'equipment_types'
    equipment_type_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    # -- Relationships -------------------
    workouts = db.relationship('Workout', backref='equipment_type_ref', lazy=True)

# --------------------------------------------------------
# - Workout Model
#---------------------------------------------------------
# Represents a single workout session
class Workout(db.Model):
    __tablename__ = 'workouts'
    workout_id = db.Column(db.Integer, primary_key=True, autoincrement=True) # Primary key for the workout
    cardio_log_id = db.Column(db.String(255), nullable=False, unique=True) # Unique identifier from the source cardio log (e.g., ErgData)
    equipment_type_id = db.Column(db.Integer, db.ForeignKey('equipment_types.equipment_type_id')) # Foreign key linking to the equipment type used
    workout_name = db.Column(db.String(255)) # User-defined name for the workout
    workout_date = db.Column(db.Date, nullable=False) # Date the workout was performed
    target_description = db.Column(db.String(100)) # Description of the workout target
    duration_seconds = db.Column(db.Numeric, nullable=True) # Total duration of the workout in seconds
    total_distance_meters = db.Column(db.Numeric, nullable=True) # Total distance covered in meters
    average_split_seconds_500m = db.Column(db.Numeric, nullable=True) # Average split time per 500 meters, in seconds
    total_isoreps = db.Column(db.Numeric, nullable=True) # Total isokinetic repetitions (specific to certain equipment)
    notes = db.Column(db.Text, nullable=True) # User-provided notes for the workout
    level = db.Column(db.Float, nullable=True) # User-defined difficulty level or intensity (float)
    
    # -- Relationships -------------------
    workout_samples = db.relationship('WorkoutSample', backref='workout', lazy='select', cascade="all, delete-orphan")
    heart_rate_samples = db.relationship('HeartRateSample', backref='workout', lazy='select', cascade="all, delete-orphan")
    workout_hr_zones = db.relationship('WorkoutHRZone', backref='workout', lazy='select', cascade="all, delete-orphan")

    # -- Representation -------------------
    def __repr__(self):
        return f"<Workout {self.workout_id} - {self.workout_name} on {self.workout_date}>"

# --------------------------------------------------------
# - MetricDescriptor Model
#---------------------------------------------------------
# Describes a type of metric recorded during a workout (e.g., 'Pace', 'Power')
class MetricDescriptor(db.Model):
    __tablename__ = 'metric_descriptors'
    metric_descriptor_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    metric_name = db.Column(db.String(100), nullable=False)
    unit_of_measure = db.Column(db.String(50), nullable=True)

    # == Table Arguments ============================================
    # Ensures that each metric name and unit combination is unique
    __table_args__ = (
        db.UniqueConstraint('metric_name', 'unit_of_measure', name='uq_metric_descriptor_name_unit'),
    )
    # -- Relationships -------------------
    samples = db.relationship('WorkoutSample', backref='metric_descriptor_ref', lazy='select')

    # -- Representation -------------------
    def __repr__(self):
        return f"<MetricDescriptor {self.metric_descriptor_id} - {self.metric_name} ({self.unit_of_measure})>"

# --------------------------------------------------------
# - WorkoutSample Model
#---------------------------------------------------------
# Stores individual data points (samples) for a workout metric over time
class WorkoutSample(db.Model):
    __tablename__ = 'workout_samples'
    sample_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    workout_id = db.Column(db.Integer, db.ForeignKey('workouts.workout_id', ondelete='CASCADE'), nullable=False)
    metric_descriptor_id = db.Column(db.Integer, db.ForeignKey('metric_descriptors.metric_descriptor_id'), nullable=False)
    time_offset_seconds = db.Column(db.Integer, nullable=False)
    value = db.Column(db.Numeric, nullable=False)

# --------------------------------------------------------
# - HeartRateSample Model
#---------------------------------------------------------
# Stores individual heart rate samples for a workout over time
class HeartRateSample(db.Model):
    __tablename__ = 'heart_rate_samples'
    hr_sample_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    workout_id = db.Column(db.Integer, db.ForeignKey('workouts.workout_id', ondelete='CASCADE'), nullable=False)
    time_offset_seconds = db.Column(db.Integer, nullable=False)
    heart_rate_bpm = db.Column(db.Integer)

# --------------------------------------------------------
# - WorkoutHRZone Model
#---------------------------------------------------------
# Stores time spent in different heart rate zones for a workout
class WorkoutHRZone(db.Model):
    __tablename__ = 'workout_hr_zones'
    workout_hr_zone_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    workout_id = db.Column(db.Integer, db.ForeignKey('workouts.workout_id', ondelete='CASCADE'), nullable=False)
    zone_name = db.Column(db.String(100), nullable=False)
    color_hex = db.Column(db.String(7))
    lower_bound_bpm = db.Column(db.Numeric)
    upper_bound_bpm = db.Column(db.Numeric)
    seconds_in_zone = db.Column(db.Numeric, nullable=False)