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

def test_successful_enrollment_and_processing(client, setup_data, dummy_image):
    from unittest.mock import patch
    headers = {"Authorization": f"Bearer {setup_data['teacher_token']}"}
    
    with patch("backend.app.domains.attendance.services.ai_engine.validate_image_quality", return_value=(True, "Success")), \
         patch("backend.app.domains.attendance.services.ai_engine.detect_and_align_faces", return_value=[{"x": 10, "y": 10, "w": 50, "h": 50, "box": (10, 60, 60, 10)}]):
        
        # 1. Enroll face
        enroll_data = {
            "student_id": str(setup_data["student"].id),
            "file": (io.BytesIO(dummy_image), "face.jpg"),
            "roll_number": "ROLL-001",
            "department": "Computer Science"
        }
        res_enroll = client.post(
            "/api/v1/attendance/enroll",
            data=enroll_data,
            content_type="multipart/form-data",
            headers=headers
        )
        assert res_enroll.status_code == 201
        
        # 2. Create session draft
        session_payload = {"latitude": 42.3601, "longitude": -71.0942, "radius": 100}
        res_sess = client.post("/api/v1/attendance/sessions", json=session_payload, headers=headers)
        assert res_sess.status_code == 201
        session_id = res_sess.get_json()["data"]["session_id"]
        
        # 3. Process classroom photo (which should match the enrolled face)
        process_data = {
            "file": (io.BytesIO(dummy_image), "classroom.jpg")
        }
        res_process = client.post(
            f"/api/v1/attendance/sessions/{session_id}/process",
            data=process_data,
            content_type="multipart/form-data",
            headers=headers
        )
        assert res_process.status_code == 200
        json_data = res_process.get_json()
        assert "matches" in json_data["data"]

def test_file_upload_validations(client, setup_data, dummy_image):
    headers = {"Authorization": f"Bearer {setup_data['teacher_token']}"}
    
    # 1. Invalid Extension
    data_ext = {
        "student_id": str(setup_data["student"].id),
        "file": (io.BytesIO(dummy_image), "face.txt")
    }
    res_ext = client.post("/api/v1/attendance/enroll", data=data_ext, content_type="multipart/form-data", headers=headers)
    assert res_ext.status_code == 400
    assert "Unsupported image format" in res_ext.get_json()["message"]

    # 2. Exceeds Size (simulate 6MB payload)
    large_bytes = b"0" * (6 * 1024 * 1024)
    data_size = {
        "student_id": str(setup_data["student"].id),
        "file": (io.BytesIO(large_bytes), "face.jpg")
    }
    res_size = client.post("/api/v1/attendance/enroll", data=data_size, content_type="multipart/form-data", headers=headers)
    assert res_size.status_code == 400
    assert "exceeds 5MB limit" in res_size.get_json()["message"]

def test_cross_tenant_isolation(client, setup_data, dummy_image):
    from backend.app import db
    from backend.app.domains.auth.models import Institution, User, Role, Permission
    
    inst_b = Institution(name="Harvard", subdomain="harvard")
    db.session.add(inst_b)
    db.session.flush()
    
    teacher_b = User(tenant_id=inst_b.id, email="teacher@harvard.edu", password_hash="dummy", first_name="H", last_name="Teacher")
    db.session.add(teacher_b)
    db.session.flush()
    
    mark_perm = Permission.query.filter_by(code="attendance:mark").first()
    role_b = Role(tenant_id=inst_b.id, name="Teacher")
    role_b.permissions = [mark_perm]
    db.session.add(role_b)
    db.session.flush()
    
    teacher_b.roles.append(role_b)
    db.session.commit()
    
    teacher_b_token = create_access_token(
        identity=str(teacher_b.id), 
        additional_claims={"tenant_id": str(inst_b.id), "permissions": ["attendance:mark"]}
    )
    
    # 1. Teacher B starts session for Tenant B
    headers_b = {"Authorization": f"Bearer {teacher_b_token}"}
    session_payload = {"latitude": 42.3601, "longitude": -71.0942, "radius": 100}
    res_sess = client.post("/api/v1/attendance/sessions", json=session_payload, headers=headers_b)
    assert res_sess.status_code == 201
    session_id = res_sess.get_json()["data"]["session_id"]
    
    # 2. Teacher A (from MIT) tries to process photo for Harvard's session_id
    headers_a = {"Authorization": f"Bearer {setup_data['teacher_token']}"}
    process_data = {"file": (io.BytesIO(dummy_image), "classroom.jpg")}
    
    res_malicious = client.post(
        f"/api/v1/attendance/sessions/{session_id}/process",
        data=process_data,
        content_type="multipart/form-data",
        headers=headers_a
    )
    # Must be 403 Forbidden!
    assert res_malicious.status_code == 403
    assert "Tenant mismatch" in res_malicious.get_json()["message"]

def test_face_approval_lifecycle_and_duplicates(client, setup_data, dummy_image):
    from unittest.mock import patch
    from backend.app import db
    from backend.app.domains.auth.models import User
    
    headers = {"Authorization": f"Bearer {setup_data['teacher_token']}"}
    
    # Set AUTO_APPROVE_FACIAL_ENROLLMENT to False
    client.application.config["AUTO_APPROVE_FACIAL_ENROLLMENT"] = False
    
    with patch("backend.app.domains.attendance.services.ai_engine.validate_image_quality", return_value=(True, "Success")), \
         patch("backend.app.domains.attendance.services.ai_engine.detect_and_align_faces", return_value=[{"x": 10, "y": 10, "w": 50, "h": 50, "box": (10, 60, 60, 10)}]):
        
        # 1. Enroll face for student (will be pending_approval)
        enroll_data = {
            "student_id": str(setup_data["student"].id),
            "file": (io.BytesIO(dummy_image), "face.jpg"),
            "roll_number": "ROLL-111"
        }
        res_enroll = client.post("/api/v1/attendance/enroll", data=enroll_data, content_type="multipart/form-data", headers=headers)
        assert res_enroll.status_code == 201
        face_id = res_enroll.get_json()["data"]["face_id"]
        
        # 2. Create session and process photo (should NOT match because face is pending approval)
        res_sess = client.post("/api/v1/attendance/sessions", json={"radius": 100}, headers=headers)
        session_id = res_sess.get_json()["data"]["session_id"]
        
        res_process_1 = client.post(
            f"/api/v1/attendance/sessions/{session_id}/process",
            data={"file": (io.BytesIO(dummy_image), "classroom.jpg")},
            content_type="multipart/form-data",
            headers=headers
        )
        assert res_process_1.status_code == 200
        matches_1 = res_process_1.get_json()["data"]["matches"]
        assert matches_1[0]["student_id"] is None  # no match
        
        # 3. Approve face
        res_approve = client.post(f"/api/v1/attendance/faces/{face_id}/approve", headers=headers)
        assert res_approve.status_code == 200
        assert res_approve.get_json()["data"]["status"] == "approved"
        
        # 4. Process again: should match now!
        res_process_2 = client.post(
            f"/api/v1/attendance/sessions/{session_id}/process",
            data={"file": (io.BytesIO(dummy_image), "classroom.jpg")},
            content_type="multipart/form-data",
            headers=headers
        )
        assert res_process_2.status_code == 200
        matches_2 = res_process_2.get_json()["data"]["matches"]
        assert matches_2[0]["student_id"] == str(setup_data["student"].id)
        
        # 5. Duplicate Check: Create another student and try to enroll the SAME face
        student_c = User(tenant_id=setup_data["institution"].id, email="student_c@mit.edu", password_hash="dummy", first_name="C", last_name="Student")
        db.session.add(student_c)
        db.session.commit()
        
        enroll_data_c = {
            "student_id": str(student_c.id),
            "file": (io.BytesIO(dummy_image), "face.jpg"),
            "roll_number": "ROLL-222"
        }
        res_enroll_c = client.post("/api/v1/attendance/enroll", data=enroll_data_c, content_type="multipart/form-data", headers=headers)
        # Should fail with 409 Conflict due to duplicate face detection!
        assert res_enroll_c.status_code == 409
        assert "reuse is prohibited" in res_enroll_c.get_json()["message"]
        
    # Reset config for other tests
    client.application.config["AUTO_APPROVE_FACIAL_ENROLLMENT"] = True

def test_cross_tenant_vulnerabilities(client, setup_data, dummy_image):
    from backend.app import db
    from backend.app.domains.auth.models import Institution, User, Role, Permission
    from backend.app.domains.attendance.models import AttendanceSession, AttendanceRecord, AttendanceCorrection
    
    # 1. Create a second institution (Tenant B) and a student belonging to Tenant B
    inst_b = Institution(name="Harvard", subdomain="harvard")
    db.session.add(inst_b)
    db.session.flush()
    
    student_b = User(tenant_id=inst_b.id, email="student@harvard.edu", password_hash="dummy", first_name="H", last_name="Student")
    db.session.add(student_b)
    db.session.commit()
    
    # 2. Teacher A (MIT) tries to enroll a face for Student B (Harvard)
    headers_a = {"Authorization": f"Bearer {setup_data['teacher_token']}"}
    enroll_data = {
        "student_id": str(student_b.id),
        "file": (io.BytesIO(dummy_image), "face.jpg"),
        "roll_number": "ROLL-HARVARD-01"
    }
    res_enroll = client.post("/api/v1/attendance/enroll", data=enroll_data, content_type="multipart/form-data", headers=headers_a)
    assert res_enroll.status_code == 403
    assert "Student does not belong to this tenant" in res_enroll.get_json()["message"]
    
    # 3. Teacher A (MIT) starts session for MIT
    session_payload = {"latitude": 42.3601, "longitude": -71.0942, "radius": 100}
    res_sess = client.post("/api/v1/attendance/sessions", json=session_payload, headers=headers_a)
    session_id = res_sess.get_json()["data"]["session_id"]
    
    # 4. Teacher A tries to confirm attendance including Student B (Harvard)
    confirm_payload = {
        "records": [
            {
                "student_id": str(student_b.id),
                "status": "present",
                "verification_method": "teacher_manual"
            }
        ]
    }
    res_confirm = client.post(f"/api/v1/attendance/sessions/{session_id}/confirm", json=confirm_payload, headers=headers_a)
    assert res_confirm.status_code == 403
    assert "does not belong to this tenant" in res_confirm.get_json()["message"]
