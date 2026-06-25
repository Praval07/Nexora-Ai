import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from backend.app.domains.lms.services import LmsService
from backend.app.core.security import require_permission
from backend.app.core.exceptions import BadRequestException

logger = logging.getLogger(__name__)

lms_bp = Blueprint("lms", __name__)

@lms_bp.route("/notes", methods=["POST"])
@jwt_required()
@require_permission("notes:upload")
def create_note():
    """
    Endpoint for uploading study notes.
    """
    data = request.get_json() or {}
    required = ["subject_id", "title", "description", "file_type", "file_url"]
    for field in required:
        if not data.get(field):
            raise BadRequestException(f"Missing field: '{field}'")
            
    claims = get_jwt()
    tenant_id = claims.get("tenant_id")
    user_id = get_jwt_identity()

    note = LmsService.create_note(
        tenant_id=tenant_id,
        subject_id=data["subject_id"],
        title=data["title"],
        description=data["description"],
        file_type=data["file_type"],
        file_url=data["file_url"],
        user_id=user_id
    )

    return jsonify({
        "status": "success",
        "message": "Note uploaded successfully",
        "data": {
            "id": str(note.id),
            "title": note.title
        }
    }), 201

@lms_bp.route("/notes", methods=["GET"])
@jwt_required()
def list_notes():
    """
    Endpoint to list uploaded study notes.
    """
    claims = get_jwt()
    tenant_id = claims.get("tenant_id")
    user_id = get_jwt_identity()
    
    subject_id = request.args.get("subject_id")
    search = request.args.get("search")

    notes = LmsService.list_notes(
        tenant_id=tenant_id,
        subject_id=subject_id,
        search=search,
        user_id=user_id
    )

    return jsonify({
        "status": "success",
        "data": {
            "notes": notes
        }
    }), 200

@lms_bp.route("/notes/<uuid:note_id>/bookmark", methods=["POST"])
@jwt_required()
def toggle_bookmark(note_id):
    """
    Endpoint to bookmark/unbookmark a study note.
    """
    user_id = get_jwt_identity()
    status = LmsService.toggle_bookmark(user_id=user_id, note_id=str(note_id))
    
    return jsonify({
        "status": "success",
        "message": "Bookmark status updated",
        "data": {
            "is_bookmarked": status
        }
    }), 200

@lms_bp.route("/assignments", methods=["POST"])
@jwt_required()
@require_permission("assignments:create")
def create_assignment():
    """
    Endpoint for creating a course assignment.
    """
    data = request.get_json() or {}
    required = ["subject_id", "title", "description", "deadline", "file_url"]
    for field in required:
        if not data.get(field):
            raise BadRequestException(f"Missing field: '{field}'")
            
    claims = get_jwt()
    tenant_id = claims.get("tenant_id")
    user_id = get_jwt_identity()

    assignment = LmsService.create_assignment(
        tenant_id=tenant_id,
        subject_id=data["subject_id"],
        title=data["title"],
        description=data["description"],
        deadline_str=data["deadline"],
        file_url=data["file_url"],
        user_id=user_id
    )

    return jsonify({
        "status": "success",
        "message": "Assignment created successfully",
        "data": {
            "id": str(assignment.id),
            "title": assignment.title
        }
    }), 201

@lms_bp.route("/assignments/<uuid:assignment_id>/submit", methods=["POST"])
@jwt_required()
def submit_assignment(assignment_id):
    """
    Endpoint for students to submit completed assignments.
    """
    data = request.get_json() or {}
    file_url = data.get("file_url")
    if not file_url:
        raise BadRequestException("Missing 'file_url'")
        
    user_id = get_jwt_identity()
    submission = LmsService.submit_assignment(
        assignment_id=str(assignment_id),
        student_id=user_id,
        file_url=file_url
    )

    return jsonify({
        "status": "success",
        "message": "Assignment submitted successfully",
        "data": {
            "submission_id": str(submission.id),
            "submitted_at": submission.submitted_at.isoformat()
        }
    }), 200

@lms_bp.route("/submissions/<uuid:submission_id>/grade", methods=["POST"])
@jwt_required()
@require_permission("assignments:grade")
def grade_submission(submission_id):
    """
    Endpoint for teachers to grade an assignment submission.
    """
    data = request.get_json() or {}
    grade = data.get("grade")
    feedback = data.get("feedback")
    
    if not grade:
        raise BadRequestException("Missing 'grade' parameter")
        
    teacher_id = get_jwt_identity()
    submission = LmsService.grade_submission(
        submission_id=str(submission_id),
        grade=grade,
        feedback=feedback,
        teacher_id=teacher_id
    )

    return jsonify({
        "status": "success",
        "message": "Submission graded successfully",
        "data": {
            "submission_id": str(submission.id),
            "grade": submission.grade
        }
    }), 200
