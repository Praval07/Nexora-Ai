import uuid
from datetime import datetime
from backend.app.core.database import db

# Helper tables for Many-to-Many relationships
role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.UUID, db.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    db.Column("permission_id", db.UUID, db.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
)

user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.UUID, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    db.Column("role_id", db.UUID, db.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
)

class Institution(db.Model):
    __tablename__ = "institutions"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    subdomain = db.Column(db.String(100), unique=True, nullable=False)
    status = db.Column(db.String(50), default="active")  # active, suspended, pending
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    users = db.relationship("User", backref="institution", cascade="all, delete-orphan")
    roles = db.relationship("Role", backref="institution", cascade="all, delete-orphan")

class User(db.Model):
    __tablename__ = "users"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID, db.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), default="active")  # active, inactive
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Many-to-many relationship with Roles
    roles = db.relationship("Role", secondary=user_roles, backref=db.backref("users", lazy="dynamic"))

    __table_args__ = (
        db.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "status": self.status,
            "roles": [role.name for role in self.roles],
            "created_at": self.created_at.isoformat()
        }

class Role(db.Model):
    __tablename__ = "roles"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID, db.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    is_system = db.Column(db.Boolean, default=False)
    
    # Many-to-many relationship with Permissions
    permissions = db.relationship("Permission", secondary=role_permissions, backref="roles")

    __table_args__ = (
        db.UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),
    )

class Permission(db.Model):
    __tablename__ = "permissions"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    code = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=False)
