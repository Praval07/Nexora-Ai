import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from backend.app.domains.chat.services import ChatService
from backend.app.domains.chat.models import ChatRoom, ChatMessage
from backend.app.core.exceptions import BadRequestException
from backend.app.core.database import db

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__)

@chat_bp.route("/rooms", methods=["POST"])
@jwt_required()
def create_room():
    """
    Endpoint to create a chat room (direct message or group channel).
    """
    data = request.get_json() or {}
    room_type = data.get("room_type", "direct")
    
    claims = get_jwt()
    tenant_id = claims.get("tenant_id")
    user_id = get_jwt_identity()

    if room_type == "direct":
        recipient_id = data.get("recipient_id")
        if not recipient_id:
            raise BadRequestException("Missing 'recipient_id'")
        room = ChatService.create_direct_room(tenant_id, user_id, recipient_id)
    else:
        name = data.get("name")
        member_ids = data.get("member_ids", [])
        if not name:
            raise BadRequestException("Missing group 'name'")
        room = ChatService.create_group_room(tenant_id, name, room_type, member_ids, user_id)

    return jsonify({
        "status": "success",
        "message": "Chat room resolved successfully",
        "data": {
            "room_id": str(room.id),
            "room_type": room.room_type,
            "name": room.name
        }
    }), 201

@chat_bp.route("/rooms", methods=["GET"])
@jwt_required()
def list_rooms():
    """
    Endpoint listing all chat rooms the user is currently member of.
    """
    import uuid
    user_id = get_jwt_identity()
    u_id = uuid.UUID(user_id)
    rooms = db.session.query(ChatRoom).join(ChatRoom.members).filter(
        ChatRoom.members.any(user_id=u_id)
    ).all()

    res = []
    for room in rooms:
        # Get latest message
        latest_msg = db.session.query(ChatMessage).filter_by(room_id=room.id).order_by(ChatMessage.created_at.desc()).first()
        res.append({
            "room_id": str(room.id),
            "name": room.name,
            "room_type": room.room_type,
            "latest_message": latest_msg.to_dict() if latest_msg else None
        })

    return jsonify({
        "status": "success",
        "data": {
            "rooms": res
        }
    }), 200

@chat_bp.route("/rooms/<uuid:room_id>/messages", methods=["GET"])
@jwt_required()
def get_room_messages(room_id):
    """
    Endpoint returning paginated message history for a specific room.
    """
    messages = db.session.query(ChatMessage).filter_by(room_id=room_id).order_by(ChatMessage.created_at.asc()).all()
    
    return jsonify({
        "status": "success",
        "data": {
            "messages": [msg.to_dict() for msg in messages]
        }
    }), 200

@chat_bp.route("/messages/<uuid:message_id>", methods=["DELETE"])
@jwt_required()
def delete_message(message_id):
    """
    Endpoint for soft deleting a chat message (moderation or self-recall).
    """
    user_id = get_jwt_identity()
    msg = ChatService.delete_message(str(message_id), user_id)
    
    return jsonify({
        "status": "success",
        "message": "Message deleted successfully",
        "data": {
            "message": msg.to_dict()
        }
    }), 200

@chat_bp.route("/block/<uuid:block_user_id>", methods=["POST"])
@jwt_required()
def block_user(block_user_id):
    """
    Endpoint to block direct messages from a specific user.
    """
    user_id = get_jwt_identity()
    ChatService.block_user(user_id, str(block_user_id))
    
    return jsonify({
        "status": "success",
        "message": "User blocked successfully"
    }), 200
