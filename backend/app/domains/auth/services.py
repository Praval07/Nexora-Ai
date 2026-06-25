import logging
from flask_jwt_extended import create_access_token, create_refresh_token
from backend.app.core.database import db
from backend.app.core.security import hash_password, check_password
from backend.app.core.exceptions import ConflictException, NotFoundException, UnauthorizedException
from backend.app.domains.auth.models import Institution, User, Role, Permission

logger = logging.getLogger(__name__)

# List of built-in system permissions
DEFAULT_PERMISSIONS = [
    {"code": "notes:upload", "description": "Can upload study notes"},
    {"code": "notes:delete", "description": "Can delete study notes"},
    {"code": "assignments:create", "description": "Can create assignments"},
    {"code": "assignments:grade", "description": "Can grade student assignments"},
    {"code": "attendance:mark", "description": "Can record classroom attendance"},
    {"code": "attendance:edit", "description": "Can edit existing attendance records"},
    {"code": "attendance:correct", "description": "Can request attendance corrections"},
    {"code": "chat:send_global", "description": "Can broadcast global announcements"},
    {"code": "users:manage", "description": "Can add/edit teachers, students, parents"}
]

class AuthService:
    @staticmethod
    def register_institution(name: str, subdomain: str, admin_email: str, admin_password: str, first_name: str, last_name: str):
        """
        Onboards a new tenant institution:
        1. Verifies subdomain uniqueness.
        2. Creates the Institution entity.
        3. Seeds system permissions and default roles.
        4. Creates the primary Organization Administrator user.
        """
        # 1. Check subdomain
        if Institution.query.filter_by(subdomain=subdomain).first():
            raise ConflictException(f"Subdomain '{subdomain}' is already taken.")
            
        # 2. Create Institution
        institution = Institution(name=name, subdomain=subdomain)
        db.session.add(institution)
        db.session.flush()  # Generates institution.id
        
        # 3. Seed Permissions (global master list if not already present)
        seeded_permissions = []
        for perm_data in DEFAULT_PERMISSIONS:
            perm = Permission.query.filter_by(code=perm_data["code"]).first()
            if not perm:
                perm = Permission(code=perm_data["code"], description=perm_data["description"])
                db.session.add(perm)
                db.session.flush()
            seeded_permissions.append(perm)

        # 4. Create default roles for this tenant
        roles = {}
        for role_name in ["Admin", "Teacher", "Student", "Parent"]:
            role = Role(tenant_id=institution.id, name=role_name, is_system=True)
            db.session.add(role)
            db.session.flush()
            roles[role_name] = role
            
        # Bind all permissions to Admin
        roles["Admin"].permissions = seeded_permissions
        
        # Bind specific permissions to Teacher
        teacher_perms = [p for p in seeded_permissions if p.code in [
            "notes:upload", "notes:delete", "assignments:create", "assignments:grade", "attendance:mark", "attendance:edit"
        ]]
        roles["Teacher"].permissions = teacher_perms

        # Bind specific permissions to Student
        student_perms = [p for p in seeded_permissions if p.code in ["attendance:correct"]]
        roles["Student"].permissions = student_perms

        # 5. Create Administrator User
        hashed = hash_password(admin_password)
        admin_user = User(
            tenant_id=institution.id,
            email=admin_email,
            password_hash=hashed,
            first_name=first_name,
            last_name=last_name
        )
        # Assign Admin role
        admin_user.roles.append(roles["Admin"])
        db.session.add(admin_user)
        
        # Commit onboarding transaction
        db.session.commit()
        logger.info(f"Onboarded institution '{name}' with subdomain '{subdomain}'")
        
        return institution, admin_user

    @staticmethod
    def authenticate_user(email: str, password: str, tenant_id: str = None, subdomain: str = None):
        """
        Authenticates user credentials and generates JWT Access + Refresh tokens.
        """
        # Resolve tenant by subdomain if tenant_id not given
        if not tenant_id and subdomain:
            inst = Institution.query.filter_by(subdomain=subdomain).first()
            if not inst:
                raise NotFoundException("Institution subdomain not found")
            tenant_id = inst.id
            
        if not tenant_id:
            raise NotFoundException("Institution tenant context is required")
            
        user = User.query.filter_by(tenant_id=tenant_id, email=email).first()
        if not user or user.status != "active":
            raise UnauthorizedException("Invalid email or password")
            
        if not check_password(password, user.password_hash):
            raise UnauthorizedException("Invalid email or password")
            
        # Generate user permissions list to bake into access token claims
        permissions = set()
        for role in user.roles:
            for perm in role.permissions:
                permissions.add(perm.code)
                
        # Build custom claims
        additional_claims = {
            "tenant_id": str(user.tenant_id),
            "permissions": list(permissions),
            "is_superadmin": False  # Reserved for global platform support admins
        }
        
        access_token = create_access_token(identity=str(user.id), additional_claims=additional_claims)
        refresh_token = create_refresh_token(identity=str(user.id), additional_claims={"tenant_id": str(user.tenant_id)})
        
        return user, access_token, refresh_token
