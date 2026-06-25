import uuid
from datetime import datetime
from backend.app.core.database import db

class ChatRoom(db.Model):
    __tablename__ = "chat_rooms"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID, db.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(255))  # None for direct messages, set for group/broadcast
    room_type = db.Column(db.String(50), nullable=False)  # direct, group, class, department, broadcast
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    members = db.relationship("ChatRoomMember", backref="room", cascade="all, delete-orphan")
    messages = db.relationship("ChatMessage", backref="room", cascade="all, delete-orphan")

class ChatRoomMember(db.Model):
    __tablename__ = "chat_room_members"
    
    room_id = db.Column(db.UUID, db.ForeignKey("chat_rooms.id", ondelete="CASCADE"), primary_key=True)
    user_id = db.Column(db.UUID, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    
    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    room_id = db.Column(db.UUID, db.ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=False)
    sender_id = db.Column(db.UUID, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    file_url = db.Column(db.String(512))  # Optional shared files or images
    is_announcement = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at = db.Column(db.DateTime)
    deleted_by = db.Column(db.UUID, db.ForeignKey("users.id"))
    
    # Relationships
    receipts = db.relationship("MessageReadReceipt", backref="message", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": str(self.id),
            "room_id": str(self.room_id),
            "sender_id": str(self.sender_id),
            "content": "[Deleted]" if self.deleted_at else self.content,
            "file_url": self.file_url if not self.deleted_at else None,
            "is_announcement": self.is_announcement,
            "created_at": self.created_at.isoformat(),
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "deleted_by": str(self.deleted_by) if self.deleted_by else None
        }

class MessageReadReceipt(db.Model):
    __tablename__ = "message_read_receipts"
    
    message_id = db.Column(db.UUID, db.ForeignKey("chat_messages.id", ondelete="CASCADE"), primary_key=True)
    user_id = db.Column(db.UUID, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    read_at = db.Column(db.DateTime, default=datetime.utcnow)

class BlockedUser(db.Model):
    __tablename__ = "blocked_users"
    
    user_id = db.Column(db.UUID, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    blocked_user_id = db.Column(db.UUID, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
