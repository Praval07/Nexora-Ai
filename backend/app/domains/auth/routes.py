import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token, get_jwt
from backend.app.domains.auth.services import AuthService
from backend.app.domains.auth.models import User, Institution
from backend.app.core.exceptions import BadRequestException

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/register-institution", methods=["POST"])
def register_institution():
    """
    Endpoint for onboarding a new institution.
    """
    data = request.get_json() or {}
    required = ["name", "subdomain", "admin_email", "admin_password", "first_name", "last_name"]
    for field in required:
        if not data.get(field):
            raise BadRequestException(f"Missing required field: '{field}'")
            
    institution, admin_user = AuthService.register_institution(
        name=data["name"],
        subdomain=data["subdomain"],
        admin_email=data["admin_email"],
        admin_password=data["admin_password"],
        first_name=data["first_name"],
        last_name=data["last_name"]
    )
    
    return jsonify({
        "status": "success",
        "message": "Institution registered successfully",
        "data": {
            "institution": {
                "id": str(institution.id),
                "name": institution.name,
                "subdomain": institution.subdomain
            },
            "admin": {
                "id": str(admin_user.id),
                "email": admin_user.email
            }
        }
    }), 201

@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Endpoint for user authentication.
    """
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")
    subdomain = data.get("subdomain")
    tenant_id = data.get("tenant_id")
    
    if not email or not password:
        raise BadRequestException("Missing email or password")
        
    user, access_token, refresh_token = AuthService.authenticate_user(
        email=email,
        password=password,
        tenant_id=tenant_id,
        subdomain=subdomain
    )
    
    return jsonify({
        "status": "success",
        "message": "Login successful",
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": user.to_dict()
        }
    }), 200

@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """
    Endpoint to issue a new access token using a valid refresh token.
    """
    user_id = get_jwt_identity()
    claims = get_jwt()
    tenant_id = claims.get("tenant_id")
    
    user = User.query.filter_by(id=user_id, tenant_id=tenant_id).first()
    if not user or user.status != "active":
        return jsonify({"status": "error", "message": "User inactive or not found"}), 401
        
    # Rebuild permissions list
    permissions = set()
    for role in user.roles:
        for perm in role.permissions:
            permissions.add(perm.code)
            
    # Generate new access token
    new_access_token = create_access_token(
        identity=str(user.id),
        additional_claims={
            "tenant_id": str(user.tenant_id),
            "permissions": list(permissions),
            "is_superadmin": False
        }
    )
    
    return jsonify({
        "status": "success",
        "data": {
            "access_token": new_access_token
        }
    }), 200

@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    """
    Returns the authenticated user's profile information.
    """
    user_id = get_jwt_identity()
    claims = get_jwt()
    tenant_id = claims.get("tenant_id")
    
    user = User.query.filter_by(id=user_id, tenant_id=tenant_id).first()
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404
        
    return jsonify({
        "status": "success",
        "data": {
            "user": user.to_dict()
        }
    }), 200
