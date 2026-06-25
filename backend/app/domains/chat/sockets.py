import logging
from flask import request
from flask_socketio import emit, join_room, leave_room
from flask_jwt_extended import decode_token
from backend.app import socketio
from backend.app.domains.chat.services import ChatService

logger = logging.getLogger(__name__)

# Track active socket connections mapped to user_ids
active_connections = {}

def get_token_from_request():
    """Extracts JWT token from query string or headers."""
    # Socket.IO connection arguments can contain token
    token = request.args.get('token')
    if not token:
        # Fallback to headers
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
    return token

@socketio.on("connect")
def handle_connect():
    """
    Validates connection token, maps session, and joins user to default rooms.
    """
    token = get_token_from_request()
    if not token:
        logger.warning("Rejected Socket connection: Missing auth token")
        return False  # Reject connection

    try:
        decoded = decode_token(token)
        user_id = decoded["sub"]
        tenant_id = decoded["tenant_id"]
        
        # Store connection mapping
        active_connections[request.sid] = {"user_id": user_id, "tenant_id": tenant_id}
        
        # Join user to personal room & tenant global room
        join_room(f"user_{user_id}")
        join_room(f"tenant_{tenant_id}")
        
        logger.info(f"Socket connected: User {user_id} on Tenant {tenant_id}")
    except Exception as e:
        logger.error(f"Socket connection error: {e}")
        return False

@socketio.on("disconnect")
def handle_disconnect():
    """Removes connection mapping on disconnect."""
    if request.sid in active_connections:
        conn = active_connections.pop(request.sid)
        logger.info(f"Socket disconnected: User {conn['user_id']}")

@socketio.on("join")
def handle_join_room(data):
    """Joins a specific chat room channel."""
    room_id = data.get("room_id")
    if not room_id:
        return
        
    sid_info = active_connections.get(request.sid)
    if not sid_info:
        return
        
    join_room(f"room_{room_id}")
    logger.info(f"User {sid_info['user_id']} joined room_{room_id}")

@socketio.on("leave")
def handle_leave_room(data):
    """Leaves a specific chat room channel."""
    room_id = data.get("room_id")
    if not room_id:
        return
    leave_room(f"room_{room_id}")

@socketio.on("send_message")
def handle_send_message(data):
    """
    Receives message payload, saves it, and broadcasts it to all room members.
    """
    sid_info = active_connections.get(request.sid)
    if not sid_info:
        emit("error", {"message": "Unauthorized session"})
        return

    room_id = data.get("room_id")
    content = data.get("content")
    file_url = data.get("file_url")
    is_announcement = data.get("is_announcement", False)

    if not room_id or not content:
        emit("error", {"message": "Invalid message parameters"})
        return

    try:
        sender_id = sid_info["user_id"]
        msg = ChatService.send_message(
            room_id=room_id,
            sender_id=sender_id,
            content=content,
            file_url=file_url,
            is_announcement=is_announcement
        )
        
        # Broadcast message to the room room_<room_id>
        emit("message", msg.to_dict(), to=f"room_{room_id}")
    except Exception as e:
        logger.error(f"Error handling send_message socket event: {e}")
        emit("error", {"message": str(e)})

@socketio.on("typing")
def handle_typing_indicator(data):
    """Broadcasts typing indicators to other members in the room."""
    sid_info = active_connections.get(request.sid)
    if not sid_info:
        return
    room_id = data.get("room_id")
    is_typing = data.get("is_typing", False)
    
    emit("typing", {
        "user_id": sid_info["user_id"],
        "is_typing": is_typing
    }, to=f"room_{room_id}", include_self=False)

@socketio.on("read_receipt")
def handle_read_receipt(data):
    """Marks message as read and broadcasts receipt metadata."""
    sid_info = active_connections.get(request.sid)
    if not sid_info:
        return
    message_id = data.get("message_id")
    room_id = data.get("room_id")
    
    try:
        ChatService.mark_read(message_id, sid_info["user_id"])
        emit("read_receipt", {
            "message_id": message_id,
            "user_id": sid_info["user_id"],
            "read_at": datetime.utcnow().isoformat()
        }, to=f"room_{room_id}")
    except Exception as e:
        logger.error(f"Error handling read receipt socket event: {e}")
