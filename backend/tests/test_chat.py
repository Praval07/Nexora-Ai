import pytest
from flask_jwt_extended import create_access_token
from backend.app import create_app, db
from backend.app.domains.auth.models import Institution, User, Role
from backend.app.domains.chat.models import ChatRoom, ChatMessage

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

    teacher_role = Role(tenant_id=inst.id, name="Teacher")
    student_role = Role(tenant_id=inst.id, name="Student")
    db.session.add_all([teacher_role, student_role])
    db.session.flush()

    teacher.roles.append(teacher_role)
    student.roles.append(student_role)
    db.session.commit()

    # Generate tokens
    teacher_token = create_access_token(
        identity=str(teacher.id), 
        additional_claims={"tenant_id": str(inst.id), "permissions": []}
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

def test_chat_lifecycle(client, setup_data):
    teacher_headers = {"Authorization": f"Bearer {setup_data['teacher_token']}"}
    student_headers = {"Authorization": f"Bearer {setup_data['student_token']}"}
    
    # Create Direct Room (Teacher with Student)
    payload = {
        "room_type": "direct",
        "recipient_id": str(setup_data["student"].id)
    }
    response = client.post("/api/v1/chat/rooms", json=payload, headers=teacher_headers)
    assert response.status_code == 201
    room_id = response.get_json()["data"]["room_id"]
    
    # Send Message (Teacher)
    msg_payload = {
        "room_id": room_id,
        "content": "Hello Student, welcome to Nexora AI!"
    }
    # Note: socket events can also be tested, but we test the service level send here via database checks or sockets trigger.
    # To test sockets, we could use socketio test client, but verifying the DB and API here is robust.
    # Let's verify we can fetch messages via GET
    from backend.app.domains.chat.services import ChatService
    ChatService.send_message(
        room_id=room_id,
        sender_id=str(setup_data["teacher"].id),
        content="Hello Student!"
    )
    
    # Fetch Messages (Student)
    response = client.get(f"/api/v1/chat/rooms/{room_id}/messages", headers=student_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["data"]["messages"]) == 1
    assert data["data"]["messages"][0]["content"] == "Hello Student!"
    message_id = data["data"]["messages"][0]["id"]
    
    # Delete Message (Teacher)
    response = client.delete(f"/api/v1/chat/messages/{message_id}", headers=teacher_headers)
    assert response.status_code == 200
    assert response.get_json()["data"]["message"]["content"] == "[Deleted]"
