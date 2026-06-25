import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from backend.app.domains.attendance.services import AttendanceService
from backend.app.core.security import require_permission
from backend.app.core.exceptions import BadRequestException

logger = logging.getLogger(__name__)

attendance_bp = Blueprint("attendance", __name__)

@attendance_bp.route("/enroll", methods=["POST"])
@jwt_required()
@require_permission("users:manage")
def enroll_student_face():
    """
    Endpoint for enrolling a student's face.
    Expects multipart/form-data with 'student_id' and 'file' fields.
    """
    student_id = request.form.get("student_id")
    file = request.files.get("file")
    
    if not student_id or not file:
        raise BadRequestException("Missing 'student_id' or upload 'file'")
        
    claims = get_jwt()
    tenant_id = claims.get("tenant_id")
    image_bytes = file.read()
    
    face = AttendanceService.enroll_student_face(
        tenant_id=tenant_id,
        student_id=student_id,
        image_bytes=image_bytes
    )
    
    return jsonify({
        "status": "success",
        "message": "Student face enrolled successfully",
        "data": {
            "face_id": str(face.id),
            "image_quality_score": face.image_quality_score
        }
    }), 201

@attendance_bp.route("/sessions", methods=["POST"])
@jwt_required()
@require_permission("attendance:mark")
def create_session():
    """
    Endpoint to start a new attendance session.
    """
    data = request.get_json() or {}
    timetable_slot_id = data.get("timetable_slot_id")
    lat = data.get("latitude")
    lng = data.get("longitude")
    radius = data.get("radius", 50)
    
    claims = get_jwt()
    tenant_id = claims.get("tenant_id")
    teacher_id = get_jwt_identity()

    session = AttendanceService.create_session(
        tenant_id=tenant_id,
        teacher_id=teacher_id,
        timetable_slot_id=timetable_slot_id,
        lat=lat,
        lng=lng,
        radius=radius
    )

    return jsonify({
        "status": "success",
        "message": "Attendance session started in draft mode",
        "data": {
            "session_id": str(session.id),
            "status": session.status,
            "date": session.date.isoformat()
        }
    }), 201

@attendance_bp.route("/sessions/<uuid:session_id>/process", methods=["POST"])
@jwt_required()
@require_permission("attendance:mark")
def process_classroom_photo(session_id):
    """
    Endpoint to upload and process a classroom photo for AI face matching.
    Expects multipart/form-data with 'file'.
    """
    file = request.files.get("file")
    if not file:
        raise BadRequestException("Missing upload 'file'")
        
    image_bytes = file.read()
    matches = AttendanceService.process_classroom_photo(
        session_id=str(session_id),
        image_bytes=image_bytes
    )

    return jsonify({
        "status": "success",
        "data": {
            "matches": matches
        }
    }), 200

@attendance_bp.route("/sessions/<uuid:session_id>/confirm", methods=["POST"])
@jwt_required()
@require_permission("attendance:mark")
def confirm_attendance(session_id):
    """
    Endpoint to finalize and lock the attendance session.
    """
    data = request.get_json() or {}
    records = data.get("records")
    if not records or not isinstance(records, list):
        raise BadRequestException("Missing list of confirmed 'records'")
        
    teacher_id = get_jwt_identity()
    ip_address = request.remote_addr or "127.0.0.1"
    user_agent = request.user_agent.string or "unknown"
    
    session = AttendanceService.confirm_attendance(
        session_id=str(session_id),
        confirmed_records=records,
        teacher_id=teacher_id,
        ip_address=ip_address,
        user_agent=user_agent
    )

    return jsonify({
        "status": "success",
        "message": "Attendance locked and finalized successfully",
        "data": {
            "session_id": str(session.id),
            "status": session.status
        }
    }), 200

@attendance_bp.route("/corrections", methods=["POST"])
@jwt_required()
def request_correction():
    """
    Endpoint for students to request attendance corrections.
    """
    data = request.get_json() or {}
    required = ["record_id", "requested_status", "reason"]
    for field in required:
        if not data.get(field):
            raise BadRequestException(f"Missing required field: '{field}'")
            
    claims = get_jwt()
    tenant_id = claims.get("tenant_id")
    student_id = get_jwt_identity()
    
    correction = AttendanceService.request_correction(
        tenant_id=tenant_id,
        student_id=student_id,
        record_id=data["record_id"],
        requested_status=data["requested_status"],
        reason=data["reason"],
        evidence_url=data.get("evidence_url")
    )
    
    return jsonify({
        "status": "success",
        "message": "Correction request submitted",
        "data": {
            "correction_id": str(correction.id),
            "status": correction.status
        }
    }), 201

@attendance_bp.route("/corrections/<uuid:correction_id>/review", methods=["POST"])
@jwt_required()
@require_permission("attendance:edit")
def review_correction(correction_id):
    """
    Endpoint for teachers to approve or reject corrections.
    """
    data = request.get_json() or {}
    status = data.get("status")
    comments = data.get("comments", "")
    
    if status not in ["approved", "rejected"]:
        raise BadRequestException("Status must be 'approved' or 'rejected'")
        
    reviewer_id = get_jwt_identity()
    ip_address = request.remote_addr or "127.0.0.1"
    user_agent = request.user_agent.string or "unknown"
    
    correction = AttendanceService.review_correction(
        correction_id=str(correction_id),
        status=status,
        comments=comments,
        reviewer_id=reviewer_id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    return jsonify({
        "status": "success",
        "message": f"Correction request reviewed: {status}",
        "data": {
            "correction_id": str(correction.id),
            "status": correction.status
        }
    }), 200
