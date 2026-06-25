import logging
from functools import wraps
import bcrypt
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
from backend.app.core.cache import cache

logger = logging.getLogger(__name__)

def hash_password(password: str) -> str:
    """Hashes a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def check_password(password: str, hashed: str) -> bool:
    """Verifies a password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception as e:
        logger.error(f"Error checking password: {e}")
        return False

def require_permission(permission_code: str):
    """
    Decorator to enforce permission checks on routes.
    Checks permissions from JWT claims, fallback to cached values in Redis.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Enforce JWT authentication
            verify_jwt_in_request()
            
            claims = get_jwt()
            user_id = claims.get("sub")
            tenant_id = claims.get("tenant_id")
            
            if not user_id or not tenant_id:
                return jsonify({"status": "error", "message": "Invalid auth token claims"}), 401
                
            # SuperAdmin bypasses all permission checks
            is_superadmin = claims.get("is_superadmin", False)
            if is_superadmin:
                return fn(*args, **kwargs)

            # Check if user has permission
            user_permissions = claims.get("permissions", [])
            
            # If not embedded in claims (e.g., token size limits), fetch from Redis cache
            if not user_permissions:
                cache_key = f"user_perms:{tenant_id}:{user_id}"
                user_permissions = cache.get(cache_key)
                
                # If cache miss, the service layer will need to load it (handled in route context)
                if user_permissions is None:
                    # In case of cache miss, we load dynamically from DB inside route or let it fail
                    # Let's import database models inside function to avoid circular imports
                    from backend.app.core.database import db
                    from sqlalchemy import text
                    
                    try:
                        # Query user permissions from database
                        query = text("""
                            SELECT p.code FROM permissions p
                            JOIN role_permissions rp ON p.id = rp.permission_id
                            JOIN user_roles ur ON rp.role_id = ur.role_id
                            WHERE ur.user_id = :user_id
                        """)
                        result = db.session.execute(query, {"user_id": user_id}).fetchall()
                        user_permissions = [row[0] for row in result]
                        # Cache in Redis for 10 minutes
                        cache.set(cache_key, user_permissions, ex_seconds=600)
                    except Exception as e:
                        logger.error(f"Failed to load permissions from DB for user {user_id}: {e}")
                        user_permissions = []

            if permission_code not in user_permissions:
                return jsonify({
                    "status": "error",
                    "message": f"Forbidden: missing permission '{permission_code}'"
                }), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator
