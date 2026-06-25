import pytest
from backend.app import create_app, db
from backend.app.domains.auth.models import Institution, User

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

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "healthy"

def test_register_institution_and_login(client):
    # Test registration
    payload = {
        "name": "MIT University",
        "subdomain": "mit",
        "admin_email": "admin@mit.edu",
        "admin_password": "securepassword123",
        "first_name": "John",
        "last_name": "Doe"
    }
    response = client.post("/api/v1/auth/register-institution", json=payload)
    assert response.status_code == 201
    
    data = response.get_json()
    assert data["status"] == "success"
    assert data["data"]["institution"]["subdomain"] == "mit"
    
    # Test login
    login_payload = {
        "email": "admin@mit.edu",
        "password": "securepassword123",
        "subdomain": "mit"
    }
    login_response = client.post("/api/v1/auth/login", json=login_payload)
    assert login_response.status_code == 200
    
    login_data = login_response.get_json()
    assert login_data["status"] == "success"
    assert "access_token" in login_data["data"]
    assert "refresh_token" in login_data["data"]
    assert login_data["data"]["user"]["email"] == "admin@mit.edu"
