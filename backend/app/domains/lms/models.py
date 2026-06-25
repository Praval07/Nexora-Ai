import uuid
from datetime import datetime
from backend.app.core.database import db

class Assignment(db.Model):
    __tablename__ = "assignments"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID, db.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    subject_id = db.Column(db.UUID, db.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    deadline = db.Column(db.DateTime, nullable=False)
    created_by = db.Column(db.UUID, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    versions = db.relationship("AssignmentVersion", backref="assignment", cascade="all, delete-orphan")
    submissions = db.relationship("AssignmentSubmission", backref="assignment", cascade="all, delete-orphan")

class AssignmentVersion(db.Model):
    __tablename__ = "assignment_versions"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    assignment_id = db.Column(db.UUID, db.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    file_url = db.Column(db.String(512), nullable=False)
    author_id = db.Column(db.UUID, db.ForeignKey("users.id"), nullable=False)
    changes_summary = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AssignmentSubmission(db.Model):
    __tablename__ = "assignment_submissions"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    assignment_id = db.Column(db.UUID, db.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    student_id = db.Column(db.UUID, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    file_url = db.Column(db.String(512), nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    grade = db.Column(db.String(10))  # e.g., 'A', 'B+', '95.0'
    feedback = db.Column(db.Text)
    graded_by = db.Column(db.UUID, db.ForeignKey("users.id"))
    graded_at = db.Column(db.DateTime)

    __table_args__ = (
        db.UniqueConstraint("assignment_id", "student_id", name="uq_assignment_student_submission"),
    )

class StudyNote(db.Model):
    __tablename__ = "study_notes"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID, db.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    subject_id = db.Column(db.UUID, db.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    file_type = db.Column(db.String(50), nullable=False)  # pdf, pptx, docx, image, video
    created_by = db.Column(db.UUID, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    versions = db.relationship("StudyNoteVersion", backref="study_note", cascade="all, delete-orphan")

class StudyNoteVersion(db.Model):
    __tablename__ = "study_note_versions"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    note_id = db.Column(db.UUID, db.ForeignKey("study_notes.id", ondelete="CASCADE"), nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    file_url = db.Column(db.String(512), nullable=False)
    author_id = db.Column(db.UUID, db.ForeignKey("users.id"), nullable=False)
    changes_summary = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class StudyNoteBookmark(db.Model):
    __tablename__ = "study_note_bookmarks"
    
    user_id = db.Column(db.UUID, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    note_id = db.Column(db.UUID, db.ForeignKey("study_notes.id", ondelete="CASCADE"), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
