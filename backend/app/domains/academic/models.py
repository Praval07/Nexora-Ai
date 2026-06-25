import uuid
from datetime import datetime
from backend.app.core.database import db

class AcademicSession(db.Model):
    __tablename__ = "academic_sessions"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID, db.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # e.g., '2026-2027'
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=False)

class Department(db.Model):
    __tablename__ = "departments"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID, db.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    
    courses = db.relationship("Course", backref="department", cascade="all, delete-orphan")

class Course(db.Model):
    __tablename__ = "courses"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID, db.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    department_id = db.Column(db.UUID, db.ForeignKey("departments.id", ondelete="SET NULL"))
    name = db.Column(db.String(255), nullable=False)
    
    classes = db.relationship("Class", backref="course", cascade="all, delete-orphan")

class Class(db.Model):
    __tablename__ = "classes"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID, db.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    course_id = db.Column(db.UUID, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    
    sections = db.relationship("Section", backref="class_ref", cascade="all, delete-orphan")

class Section(db.Model):
    __tablename__ = "sections"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID, db.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    class_id = db.Column(db.UUID, db.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    
    subjects = db.relationship("Subject", backref="section", cascade="all, delete-orphan")

class Subject(db.Model):
    __tablename__ = "subjects"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID, db.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    section_id = db.Column(db.UUID, db.ForeignKey("sections.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(50), nullable=False)
