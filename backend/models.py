from datetime import datetime

from sqlalchemy.inspection import inspect

from .extensions import db
from .services.time_service import beijing_now


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=beijing_now, onupdate=beijing_now, nullable=False
    )

    def to_dict(self):
        data = {}
        for column in inspect(self).mapper.column_attrs:
            value = getattr(self, column.key)
            if isinstance(value, datetime):
                data[column.key] = value.isoformat()
            else:
                data[column.key] = value
        return data


class User(db.Model, TimestampMixin):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False, default="user")
    email = db.Column(db.String(128))
    status = db.Column(db.String(16), nullable=False, default="active")
    active_model_id = db.Column(db.Integer)


class DomainSample(db.Model, TimestampMixin):
    __tablename__ = "domain_sample"

    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255), nullable=False, index=True)
    url = db.Column(db.String(1024))
    label = db.Column(db.String(32), nullable=False)
    sample_type = db.Column(db.String(32), nullable=False)
    source = db.Column(db.String(128))
    is_trainable = db.Column(db.Boolean, default=True, nullable=False)
    remark = db.Column(db.String(255))


class ModelInfo(db.Model, TimestampMixin):
    __tablename__ = "model_info"

    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(64), nullable=False)
    model_type = db.Column(db.String(64), nullable=False)
    version = db.Column(db.String(32), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    feature_type = db.Column(db.String(64), nullable=False)
    storage_type = db.Column(db.String(32), nullable=False, default="file")
    model_blob = db.Column(db.LargeBinary)
    owner_id = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    remark = db.Column(db.String(255))

    def to_dict(self):
        data = {}
        for column in inspect(self).mapper.column_attrs:
            if column.key == "model_blob":
                continue
            value = getattr(self, column.key)
            if isinstance(value, datetime):
                data[column.key] = value.isoformat()
            else:
                data[column.key] = value
        data["has_model_blob"] = self.storage_type == "database"
        return data


class TrainingTask(db.Model, TimestampMixin):
    __tablename__ = "training_task"

    id = db.Column(db.Integer, primary_key=True)
    model_type = db.Column(db.String(64), nullable=False)
    dataset_size = db.Column(db.Integer, nullable=False, default=0)
    train_config = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(32), nullable=False, default="pending")
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    log_text = db.Column(db.Text)

    creator = db.relationship("User", backref=db.backref("training_tasks", lazy=True))


class EvaluationMetric(db.Model, TimestampMixin):
    __tablename__ = "evaluation_metric"

    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.Integer, db.ForeignKey("model_info.id"), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey("training_task.id"))
    accuracy = db.Column(db.Float)
    precision_value = db.Column(db.Float)
    recall_value = db.Column(db.Float)
    f1_value = db.Column(db.Float)
    auc_value = db.Column(db.Float)
    confusion_matrix = db.Column(db.Text)

    model = db.relationship("ModelInfo", backref=db.backref("metrics", lazy=True))
    task = db.relationship("TrainingTask", backref=db.backref("metrics", lazy=True))


class FeatureRecord(db.Model, TimestampMixin):
    __tablename__ = "feature_record"

    id = db.Column(db.Integer, primary_key=True)
    sample_id = db.Column(db.Integer, db.ForeignKey("domain_sample.id"), nullable=False)
    domain_length = db.Column(db.Integer)
    entropy_value = db.Column(db.Float)
    digit_ratio = db.Column(db.Float)
    hyphen_count = db.Column(db.Integer)
    dot_count = db.Column(db.Integer)
    subdomain_count = db.Column(db.Integer)
    sequence_length = db.Column(db.Integer)

    sample = db.relationship("DomainSample", backref=db.backref("feature_records", lazy=True))


class DetectionRecord(db.Model, TimestampMixin):
    __tablename__ = "detection_record"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    input_text = db.Column(db.String(1024), nullable=False)
    parsed_domain = db.Column(db.String(255), nullable=False)
    predict_label = db.Column(db.String(32), nullable=False)
    risk_score = db.Column(db.Float, nullable=False)
    risk_level = db.Column(db.String(32), nullable=False)
    model_id = db.Column(db.Integer, db.ForeignKey("model_info.id"))
    detect_time = db.Column(db.DateTime, default=beijing_now, nullable=False)
    explain_text = db.Column(db.Text)

    user = db.relationship("User", backref=db.backref("detection_records", lazy=True))
    model = db.relationship("ModelInfo", backref=db.backref("detection_records", lazy=True))


class OperationLog(db.Model, TimestampMixin):
    __tablename__ = "operation_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    action_type = db.Column(db.String(64), nullable=False)
    target_type = db.Column(db.String(64))
    target_id = db.Column(db.String(64))
    detail = db.Column(db.Text)
    ip_address = db.Column(db.String(64))

    user = db.relationship("User", backref=db.backref("operation_logs", lazy=True))


class ReviewFeedback(db.Model, TimestampMixin):
    __tablename__ = "review_feedback"

    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey("detection_record.id"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    review_result = db.Column(db.String(32), nullable=False)
    correct_label = db.Column(db.String(32))
    comment = db.Column(db.Text)

    record = db.relationship("DetectionRecord", backref=db.backref("review_feedback", lazy=True))
    reviewer = db.relationship("User", backref=db.backref("review_feedback", lazy=True))
