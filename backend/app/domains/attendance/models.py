import uuid
from datetime import datetime, timezone
from backend.app.core.database import db

class StudentProfile(db.Model):
    __tablename__ = "student_profiles"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID, db.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = db.Column(db.UUID, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    roll_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    mobile_number = db.Column(db.String(20))
    department = db.Column(db.String(100))
    course = db.Column(db.String(100))
    semester_grade = db.Column(db.String(50))
    section = db.Column(db.String(50), index=True)
    profile_photo_url = db.Column(db.String(512))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class StudentFace(db.Model):
    __tablename__ = "student_faces"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID, db.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = db.Column(db.UUID, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    embedding = db.Column(db.JSON, nullable=False)  # Stored as encrypted JSON list of 128 floats for security
    image_quality_score = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default="approved", index=True)  # approved, pending_approval, rejected, superseded
    approved_by = db.Column(db.UUID, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class AttendanceSession(db.Model):
    __tablename__ = "attendance_sessions"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID, db.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    timetable_slot_id = db.Column(db.UUID, db.ForeignKey("timetable_slots.id", ondelete="SET NULL"))
    teacher_id = db.Column(db.UUID, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = db.Column(db.Date, default=lambda: datetime.now(timezone.utc).date(), nullable=False, index=True)
    start_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    gps_latitude = db.Column(db.Numeric(9,6))
    gps_longitude = db.Column(db.Numeric(9,6))
    gps_radius_meters = db.Column(db.Integer, default=50)
    status = db.Column(db.String(50), default="draft", index=True)  # draft, confirmed
    
    records = db.relationship("AttendanceRecord", backref="session", cascade="all, delete-orphan")

class AttendanceRecord(db.Model):
    __tablename__ = "attendance_records"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID, db.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = db.Column(db.UUID, db.ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = db.Column(db.UUID, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = db.Column(db.String(50), nullable=False, index=True)  # present, absent, late, excused, unknown
    verification_method = db.Column(db.String(50), nullable=False)  # face_auto, teacher_manual, gps_only
    confidence_score = db.Column(db.Float)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)  # Soft delete support
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("session_id", "student_id", name="uq_session_student_attendance"),
    )

class AttendanceCorrection(db.Model):
    __tablename__ = "attendance_corrections"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID, db.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = db.Column(db.UUID, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    record_id = db.Column(db.UUID, db.ForeignKey("attendance_records.id", ondelete="CASCADE"))
    requested_status = db.Column(db.String(50), nullable=False)  # present, excused
    reason = db.Column(db.Text, nullable=False)
    evidence_url = db.Column(db.String(512))
    status = db.Column(db.String(50), default="pending", index=True)  # pending, approved, rejected
    reviewed_by = db.Column(db.UUID, db.ForeignKey("users.id"))
    review_comments = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
