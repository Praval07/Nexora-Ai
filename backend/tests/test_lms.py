import pytest
from datetime import datetime, timedelta
from flask_jwt_extended import create_access_token
from backend.app import create_app, db
from backend.app.domains.auth.models import Institution, User, Role, Permission
from backend.app.domains.academic.models import Subject, Section, Class, Course
from backend.app.domains.lms.models import Assignment, AssignmentSubmission, StudyNote

@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def setup_data(app):
    # Create institution
    inst = Institution(name="MIT", subdomain="mit")
    db.session.add(inst)
    db.session.flush()
    
    # Create teacher and student
    teacher = User(tenant_id=inst.id, email="teacher@mit.edu", password_hash="dummy", first_name="T", last_name="Teacher")
    student = User(tenant_id=inst.id, email="student@mit.edu", password_hash="dummy", first_name="S", last_name="Student")
    db.session.add_all([teacher, student])
    db.session.flush()

    # Create roles and permissions
    upload_perm = Permission(code="notes:upload", description="upload notes")
    create_perm = Permission(code="assignments:create", description="create assignments")
    grade_perm = Permission(code="assignments:grade", description="grade submissions")
    db.session.add_all([upload_perm, create_perm, grade_perm])
    db.session.flush()

    teacher_role = Role(tenant_id=inst.id, name="Teacher")
    teacher_role.permissions = [upload_perm, create_perm, grade_perm]
    
    student_role = Role(tenant_id=inst.id, name="Student")
    
    db.session.add_all([teacher_role, student_role])
    db.session.flush()

    teacher.roles.append(teacher_role)
    student.roles.append(student_role)
    
    # Create academic entities
    course = Course(tenant_id=inst.id, name="Computer Science")
    db.session.add(course)
    db.session.flush()

    cls = Class(tenant_id=inst.id, course_id=course.id, name="Year 1")
    db.session.add(cls)
    db.session.flush()

    sec = Section(tenant_id=inst.id, class_id=cls.id, name="Sec A")
    db.session.add(sec)
    db.session.flush()

    subj = Subject(tenant_id=inst.id, section_id=sec.id, name="Python Programming", code="CS101")
    db.session.add(subj)
    db.session.commit()

    # Generate tokens
    teacher_token = create_access_token(
        identity=str(teacher.id), 
        additional_claims={"tenant_id": str(inst.id), "permissions": ["notes:upload", "assignments:create", "assignments:grade"]}
    )
    student_token = create_access_token(
        identity=str(student.id), 
        additional_claims={"tenant_id": str(inst.id), "permissions": []}
    )

    return {
        "institution": inst,
        "teacher": teacher,
        "student": student,
        "subject": subj,
        "teacher_token": teacher_token,
        "student_token": student_token
    }

def test_notes_creation_and_listing(client, setup_data):
    headers = {"Authorization": f"Bearer {setup_data['teacher_token']}"}
    
    # Create Note
    payload = {
        "subject_id": str(setup_data["subject"].id),
        "title": "Lecture 1 Notes",
        "description": "Introduction to Python syntax",
        "file_type": "pdf",
        "file_url": "http://cloudinary.com/note1.pdf"
    }
    response = client.post("/api/v1/lms/notes", json=payload, headers=headers)
    assert response.status_code == 201
    
    # List Notes
    response = client.get("/api/v1/lms/notes", headers=headers)
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["data"]["notes"]) == 1
    assert data["data"]["notes"][0]["title"] == "Lecture 1 Notes"

def test_assignment_lifecycle(client, setup_data):
    teacher_headers = {"Authorization": f"Bearer {setup_data['teacher_token']}"}
    student_headers = {"Authorization": f"Bearer {setup_data['student_token']}"}
    
    # Create Assignment
    deadline = (datetime.utcnow() + timedelta(days=2)).isoformat()
    payload = {
        "subject_id": str(setup_data["subject"].id),
        "title": "HW 1: Basic Variables",
        "description": "Solve Python assignments",
        "deadline": deadline,
        "file_url": "http://cloudinary.com/hw1.pdf"
    }
    response = client.post("/api/v1/lms/assignments", json=payload, headers=teacher_headers)
    assert response.status_code == 201
    assignment_id = response.get_json()["data"]["id"]
    
    # Submit Assignment (Student)
    sub_payload = {"file_url": "http://cloudinary.com/student_sub1.pdf"}
    response = client.post(f"/api/v1/lms/assignments/{assignment_id}/submit", json=sub_payload, headers=student_headers)
    assert response.status_code == 200
    submission_id = response.get_json()["data"]["submission_id"]
    
    # Grade Submission (Teacher)
    grade_payload = {
        "grade": "A+",
        "feedback": "Excellent work!"
    }
    response = client.post(f"/api/v1/lms/submissions/{submission_id}/grade", json=grade_payload, headers=teacher_headers)
    assert response.status_code == 200
    assert response.get_json()["data"]["grade"] == "A+"
