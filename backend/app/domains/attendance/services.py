import uuid
from datetime import datetime
from backend.app.core.database import db
from backend.app.domains.attendance.models import StudentFace, AttendanceSession, AttendanceRecord, AttendanceCorrection
from backend.app.domains.attendance.ai_engine import AIAttendanceEngine
from backend.app.domains.auth.models import User, AuditLog
from backend.app.core.exceptions import NotFoundException, BadRequestException, ConflictException

# Instantiate global AI engine
ai_engine = AIAttendanceEngine()

class AttendanceService:
    @staticmethod
    def enroll_student_face(tenant_id: str, student_id: str, image_bytes: bytes):
        """
        Enrolls a new face signature for a student.
        1. Decodes and runs quality/blur checks on the image.
        2. Detects and aligns the face.
        3. Generates and stores the 128-float embedding vector in the DB.
        """
        t_uuid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
        s_uuid = uuid.UUID(student_id) if isinstance(student_id, str) else student_id

        # Decode image using OpenCV
        import cv2
        import numpy as np
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            raise BadRequestException("Failed to decode image bytes")

        # 1. Quality Validation
        is_ok, quality_msg = ai_engine.validate_image_quality(img)
        if not is_ok:
            raise BadRequestException(f"Image quality check failed: {quality_msg}")

        # Calculate variance of laplacian as quality score
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        quality_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # 2. Face Detection & Alignment
        faces = ai_engine.detect_and_align_faces(img)
        if len(faces) == 0:
            raise BadRequestException("No face detected in the enrollment image")
        if len(faces) > 1:
            raise BadRequestException("Multiple faces detected. Enrollment requires a single face image.")

        # 3. Generate Embedding
        embedding = ai_engine.generate_embeddings(img, faces[0]["box"])
        
        # Save to database
        face_record = StudentFace(
            tenant_id=t_uuid,
            student_id=s_uuid,
            embedding=embedding,
            image_quality_score=quality_score
        )
        db.session.add(face_record)
        db.session.commit()
        return face_record

    @staticmethod
    def create_session(tenant_id: str, teacher_id: str, timetable_slot_id: str = None, lat: float = None, lng: float = None, radius: int = 50):
        """
        Creates a new attendance session draft.
        """
        t_uuid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
        teach_uuid = uuid.UUID(teacher_id) if isinstance(teacher_id, str) else teacher_id
        slot_uuid = uuid.UUID(timetable_slot_id) if timetable_slot_id else None

        session = AttendanceSession(
            tenant_id=t_uuid,
            teacher_id=teach_uuid,
            timetable_slot_id=slot_uuid,
            gps_latitude=lat,
            gps_longitude=lng,
            gps_radius_meters=radius,
            status="draft"
        )
        db.session.add(session)
        db.session.commit()
        return session

    @staticmethod
    def process_classroom_photo(session_id: str, image_bytes: bytes):
        """
        Processes a classroom image and returns a match report.
        Reads all active student faces registered under the session's tenant.
        """
        sess_uuid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id
        session = db.session.get(AttendanceSession, sess_uuid)
        if not session:
            raise NotFoundException("Attendance session not found")

        # Load all registered student face embeddings for this tenant
        faces = StudentFace.query.filter_by(tenant_id=session.tenant_id, status="approved").all()
        
        # Group embeddings by student ID
        student_map = {}
        for face in faces:
            s_str = str(face.student_id)
            if s_str not in student_map:
                student_map[s_str] = {"student_id": face.student_id, "embeddings": []}
            student_map[s_str]["embeddings"].append(face.embedding)

        registered_students = list(student_map.values())

        # Process image using AI engine
        try:
            matches = ai_engine.process_classroom_image(image_bytes, registered_students)
            return matches
        except Exception as e:
            raise BadRequestException(str(e))

    @staticmethod
    def confirm_attendance(session_id: str, confirmed_records: list[dict], teacher_id: str, ip_address: str, user_agent: str):
        """
        Locks the session and saves final attendance records.
        Also records an audit log.
        """
        sess_uuid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id
        teach_uuid = uuid.UUID(teacher_id) if isinstance(teacher_id, str) else teacher_id

        session = db.session.get(AttendanceSession, sess_uuid)
        if not session:
            raise NotFoundException("Attendance session not found")
        if session.status == "confirmed":
            raise ConflictException("Attendance session has already been finalized")

        # Lock session
        session.status = "confirmed"

        # Save student records
        for record in confirmed_records:
            s_uuid = uuid.UUID(record["student_id"])
            status = record["status"]  # present, absent, late, excused
            method = record.get("verification_method", "face_auto")
            score = record.get("confidence_score")

            # Check duplicate database insertion
            existing = AttendanceRecord.query.filter_by(session_id=session.id, student_id=s_uuid).first()
            if existing:
                existing.status = status
                existing.verification_method = method
                existing.confidence_score = score
            else:
                new_record = AttendanceRecord(
                    tenant_id=session.tenant_id,
                    session_id=session.id,
                    student_id=s_uuid,
                    status=status,
                    verification_method=method,
                    confidence_score=score
                )
                db.session.add(new_record)

        # Write immutable audit log
        audit = AuditLog(
            tenant_id=session.tenant_id,
            user_id=teach_uuid,
            ip_address=ip_address,
            user_agent=user_agent,
            action="attendance:confirm",
            previous_value={"status": "draft"},
            new_value={"status": "confirmed", "records_count": len(confirmed_records)}
        )
        db.session.add(audit)
        db.session.commit()
        return session

    @staticmethod
    def request_correction(tenant_id: str, student_id: str, record_id: str, requested_status: str, reason: str, evidence_url: str = None):
        """
        Allows students to request correction on their attendance status.
        """
        t_uuid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
        s_uuid = uuid.UUID(student_id) if isinstance(student_id, str) else student_id
        r_uuid = uuid.UUID(record_id) if isinstance(record_id, str) else record_id

        # Verify record exists
        record = db.session.get(AttendanceRecord, r_uuid)
        if not record or record.student_id != s_uuid:
            raise NotFoundException("Attendance record not found")

        correction = AttendanceCorrection(
            tenant_id=t_uuid,
            student_id=s_uuid,
            record_id=r_uuid,
            requested_status=requested_status,
            reason=reason,
            evidence_url=evidence_url,
            status="pending"
        )
        db.session.add(correction)
        db.session.commit()
        return correction

    @staticmethod
    def review_correction(correction_id: str, status: str, comments: str, reviewer_id: str, ip_address: str, user_agent: str):
        """
        Allows teachers/admins to approve or reject a correction request.
        Updates attendance status if approved and logs an audit.
        """
        c_uuid = uuid.UUID(correction_id) if isinstance(correction_id, str) else correction_id
        rev_uuid = uuid.UUID(reviewer_id) if isinstance(reviewer_id, str) else reviewer_id

        correction = db.session.get(AttendanceCorrection, c_uuid)
        if not correction:
            raise NotFoundException("Correction request not found")
        if correction.status != "pending":
            raise ConflictException("Correction request has already been reviewed")

        previous_status = correction.status
        correction.status = status
        correction.reviewed_by = rev_uuid
        correction.review_comments = comments

        if status == "approved":
            record = db.session.get(AttendanceRecord, correction.record_id)
            if record:
                old_status = record.status
                record.status = correction.requested_status
                
                # Write Audit Log for attendance manual correction
                audit = AuditLog(
                    tenant_id=correction.tenant_id,
                    user_id=rev_uuid,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    action="attendance:correction_approved",
                    previous_value={"record_id": str(record.id), "status": old_status},
                    new_value={"record_id": str(record.id), "status": record.status}
                )
                db.session.add(audit)

        db.session.commit()
        return correction
