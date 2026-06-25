import uuid
from datetime import datetime
from backend.app.core.database import db

class StudentFace(db.Model):
    __tablename__ = "student_faces"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID, db.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    student_id = db.Column(db.UUID, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    embedding = db.Column(db.JSON, nullable=False)  # Stored as JSON list of 128 floats for cross-db compatibility
    image_quality_score = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default="approved")  # approved, pending_approval, rejected
    approved_by = db.Column(db.UUID, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AttendanceSession(db.Model):
    __tablename__ = "attendance_sessions"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID, db.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    timetable_slot_id = db.Column(db.UUID, db.ForeignKey("timetable_slots.id", ondelete="SET NULL"))
    teacher_id = db.Column(db.UUID, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow().date, nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    gps_latitude = db.Column(db.Numeric(9,6))
    gps_longitude = db.Column(db.Numeric(9,6))
    gps_radius_meters = db.Column(db.Integer, default=50)
    status = db.Column(db.String(50), default="draft")  # draft, confirmed
    
    records = db.relationship("AttendanceRecord", backref="session", cascade="all, delete-orphan")

class AttendanceRecord(db.Model):
    __tablename__ = "attendance_records"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID, db.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    session_id = db.Column(db.UUID, db.ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False)
    student_id = db.Column(db.UUID, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = db.Column(db.String(50), nullable=False)  # present, absent, late, excused, unknown
    verification_method = db.Column(db.String(50), nullable=False)  # face_auto, teacher_manual, gps_only
    confidence_score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("session_id", "student_id", name="uq_session_student_attendance"),
    )

class AttendanceCorrection(db.Model):
    __tablename__ = "attendance_corrections"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID, db.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    student_id = db.Column(db.UUID, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    record_id = db.Column(db.UUID, db.ForeignKey("attendance_records.id", ondelete="CASCADE"))
    requested_status = db.Column(db.String(50), nullable=False)  # present, excused
    reason = db.Column(db.Text, nullable=False)
    evidence_url = db.Column(db.String(512))
    status = db.Column(db.String(50), default="pending")  # pending, approved, rejected
    reviewed_by = db.Column(db.UUID, db.ForeignKey("users.id"))
    review_comments = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
