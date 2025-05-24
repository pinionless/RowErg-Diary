from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID
import uuid as py_uuid
from datetime import datetime, timezone

db = SQLAlchemy()

class EquipmentType(db.Model):
    __tablename__ = 'equipment_types'
    equipment_type_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    workouts = db.relationship('Workout', backref='equipment_type_ref', lazy=True)

class PhysicalActivity(db.Model):
    __tablename__ = 'physical_activities'
    physical_activity_guid = db.Column(UUID(as_uuid=True), primary_key=True, default=py_uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    workouts = db.relationship('Workout', backref='physical_activity_ref', lazy=True)

class Workout(db.Model):
    __tablename__ = 'workouts'
    workout_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cardio_log_id = db.Column(db.String(255), nullable=False, unique=True)
    equipment_type_id = db.Column(db.Integer, db.ForeignKey('equipment_types.equipment_type_id'))
    workout_name = db.Column(db.String(255))
    workout_date = db.Column(db.Date, nullable=False)
    target_description = db.Column(db.String(100))
    is_favorite = db.Column(db.Boolean)
    physical_activity_guid = db.Column(UUID(as_uuid=True), db.ForeignKey('physical_activities.physical_activity_guid'))
    n_eser = db.Column(db.Integer)
    n_attr = db.Column(db.Integer)
    imported_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    metric_descriptors = db.relationship('MetricDescriptor', backref='workout', lazy='select', cascade="all, delete-orphan")
    workout_samples = db.relationship('WorkoutSample', backref='workout', lazy='select', cascade="all, delete-orphan")
    heart_rate_samples = db.relationship('HeartRateSample', backref='workout', lazy='select', cascade="all, delete-orphan")
    workout_hr_zones = db.relationship('WorkoutHRZone', backref='workout', lazy='select', cascade="all, delete-orphan")
    workout_summary_data = db.relationship('WorkoutSummaryData', backref='workout', lazy='select', cascade="all, delete-orphan")


    def __repr__(self):
        return f"<Workout {self.workout_id} - {self.workout_name} on {self.workout_date}>"

class MetricDescriptor(db.Model):
    __tablename__ = 'metric_descriptors'
    metric_descriptor_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    workout_id = db.Column(db.Integer, db.ForeignKey('workouts.workout_id'), nullable=False)
    json_index = db.Column(db.Integer, nullable=False)
    metric_name = db.Column(db.String(100), nullable=False)
    unit_of_measure = db.Column(db.String(50))
    __table_args__ = (db.UniqueConstraint('workout_id', 'json_index', name='uq_metric_descriptors_workout_json_index'),
                      db.UniqueConstraint('workout_id', 'metric_name', name='uq_metric_descriptors_workout_metric_name'))
    samples = db.relationship('WorkoutSample', backref='metric_descriptor_ref', lazy='select', cascade="all, delete-orphan")

class WorkoutSample(db.Model):
    __tablename__ = 'workout_samples'
    sample_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    workout_id = db.Column(db.Integer, db.ForeignKey('workouts.workout_id'), nullable=False)
    metric_descriptor_id = db.Column(db.Integer, db.ForeignKey('metric_descriptors.metric_descriptor_id'), nullable=False)
    time_offset_seconds = db.Column(db.Integer, nullable=False)
    value = db.Column(db.Numeric, nullable=False)

class HeartRateSample(db.Model):
    __tablename__ = 'heart_rate_samples'
    hr_sample_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    workout_id = db.Column(db.Integer, db.ForeignKey('workouts.workout_id'), nullable=False)
    time_offset_seconds = db.Column(db.Integer, nullable=False)
    heart_rate_bpm = db.Column(db.Integer)

class WorkoutHRZone(db.Model):
    __tablename__ = 'workout_hr_zones'
    workout_hr_zone_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    workout_id = db.Column(db.Integer, db.ForeignKey('workouts.workout_id'), nullable=False)
    zone_name = db.Column(db.String(100), nullable=False)
    color_hex = db.Column(db.String(7))
    lower_bound_bpm = db.Column(db.Numeric)
    upper_bound_bpm = db.Column(db.Numeric)
    seconds_in_zone = db.Column(db.Numeric, nullable=False)

class WorkoutSummaryData(db.Model):
    __tablename__ = 'workout_summary_data'
    summary_data_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    workout_id = db.Column(db.Integer, db.ForeignKey('workouts.workout_id'), nullable=False)
    property_key = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    value_text = db.Column(db.String(255))
    unit_of_measure = db.Column(db.String(50))
    raw_value = db.Column(db.Numeric, nullable=False)
