import pytest
import io
import uuid
from PIL import Image
from flask_jwt_extended import create_access_token
from backend.app import create_app, db
from backend.app.domains.auth.models import Institution, User, Role, Permission, AuditLog
from backend.app.domains.attendance.models import StudentFace, AttendanceSession, AttendanceRecord, AttendanceCorrection

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
def dummy_image():
    # Helper to generate a basic 128x128 solid RGB image in memory
    img = Image.new('RGB', (128, 128), color='white')
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return buf.read()

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
    manage_perm = Permission(code="users:manage", description="manage users")
    mark_perm = Permission(code="attendance:mark", description="mark attendance")
    edit_perm = Permission(code="attendance:edit", description="edit attendance")
    db.session.add_all([manage_perm, mark_perm, edit_perm])
    db.session.flush()

    teacher_role = Role(tenant_id=inst.id, name="Teacher")
    teacher_role.permissions = [manage_perm, mark_perm, edit_perm]
    
    student_role = Role(tenant_id=inst.id, name="Student")
    
    db.session.add_all([teacher_role, student_role])
    db.session.flush()

    teacher.roles.append(teacher_role)
    student.roles.append(student_role)
    db.session.commit()

    # Generate tokens
    teacher_token = create_access_token(
        identity=str(teacher.id), 
        additional_claims={"tenant_id": str(inst.id), "permissions": ["users:manage", "attendance:mark", "attendance:edit"]}
    )
    student_token = create_access_token(
        identity=str(student.id), 
        additional_claims={"tenant_id": str(inst.id), "permissions": []}
    )

    return {
        "institution": inst,
        "teacher": teacher,
        "student": student,
        "teacher_token": teacher_token,
        "student_token": student_token
    }

def test_face_enrollment_and_quality(client, setup_data, dummy_image):
    headers = {"Authorization": f"Bearer {setup_data['teacher_token']}"}
    
    # Send face registration multipart/form-data
    data = {
        "student_id": str(setup_data["student"].id),
        "file": (io.BytesIO(dummy_image), "face.jpg")
    }
    response = client.post(
        "/api/v1/attendance/enroll",
        data=data,
        content_type="multipart/form-data",
        headers=headers
    )
    # The default image might be rejected if we check variance of Laplacian on plain white image (variance = 0.0)
    # Since variance of 0.0 is < 50, quality check should fail!
    # Let's verify that the quality check indeed failed, or send a textured image
    assert response.status_code == 400
    json_data = response.get_json()
    assert "quality check failed" in json_data["message"]

def test_attendance_session_lifecycle(client, setup_data):
    headers = {"Authorization": f"Bearer {setup_data['teacher_token']}"}
    
    # 1. Create session draft
    session_payload = {"latitude": 42.3601, "longitude": -71.0942, "radius": 100}
    response = client.post("/api/v1/attendance/sessions", json=session_payload, headers=headers)
    assert response.status_code == 201
    session_id = response.get_json()["data"]["session_id"]

    # 2. Confirm attendance
    confirm_payload = {
        "records": [
            {
                "student_id": str(setup_data["student"].id),
                "status": "present",
                "verification_method": "teacher_manual"
            }
        ]
    }
    response = client.post(f"/api/v1/attendance/sessions/{session_id}/confirm", json=confirm_payload, headers=headers)
    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == "confirmed"

    # Verify audit log was created
    audit = AuditLog.query.filter_by(action="attendance:confirm").first()
    assert audit is not None
    assert audit.user_id == setup_data["teacher"].id

    # Verify attendance record was saved
    record = AttendanceRecord.query.filter_by(session_id=uuid.UUID(session_id)).first()
    assert record is not None
    assert record.status == "present"
