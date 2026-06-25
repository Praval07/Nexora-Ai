import uuid
import base64
import json
import hashlib
from datetime import datetime
from flask import current_app
from backend.app.core.database import db
from backend.app.domains.attendance.models import StudentFace, StudentProfile, AttendanceSession, AttendanceRecord, AttendanceCorrection
from backend.app.domains.attendance.ai_engine import AIAttendanceEngine
from backend.app.domains.auth.models import User, AuditLog
from backend.app.core.exceptions import NotFoundException, BadRequestException, ConflictException, ForbiddenException

# Instantiate global AI engine
ai_engine = AIAttendanceEngine()

class AttendanceService:
    @staticmethod
    def _get_encryption_key():
        # Get key from Flask config, default to a robust fallback key
        return current_app.config.get("SECRET_KEY", "nexora-ai-default-key-32bytes-long")

    @staticmethod
    def encrypt_embedding(embedding: list[float]) -> dict:
        key = AttendanceService._get_encryption_key()
        plain_bytes = json.dumps(embedding).encode('utf-8')
        key_hash = hashlib.sha256(key.encode('utf-8')).digest()
        cipher_bytes = bytearray(len(plain_bytes))
        for i in range(len(plain_bytes)):
            block_hash = hashlib.sha256(key_hash + str(i // 32).encode('utf-8')).digest()
            cipher_bytes[i] = plain_bytes[i] ^ block_hash[i % 32]
        return {
            "encrypted": True,
            "ciphertext": base64.b64encode(cipher_bytes).decode('utf-8')
        }

    @staticmethod
    def decrypt_embedding(encrypted_data: dict) -> list[float]:
        if not isinstance(encrypted_data, dict) or not encrypted_data.get("encrypted"):
            return encrypted_data
        key = AttendanceService._get_encryption_key()
        cipher_bytes = base64.b64decode(encrypted_data["ciphertext"])
        key_hash = hashlib.sha256(key.encode('utf-8')).digest()
        plain_bytes = bytearray(len(cipher_bytes))
        for i in range(len(cipher_bytes)):
            block_hash = hashlib.sha256(key_hash + str(i // 32).encode('utf-8')).digest()
            plain_bytes[i] = cipher_bytes[i] ^ block_hash[i % 32]
        return json.loads(plain_bytes.decode('utf-8'))
    @staticmethod
    def enroll_student_face(tenant_id: str, student_id: str, image_bytes: bytes,
                            roll_number: str = None, mobile_number: str = None,
                            department: str = None, course: str = None,
                            semester_grade: str = None, section: str = None):
        """
        Enrolls a new face signature for a student.
        1. Decodes and runs quality/blur checks on the image.
        2. Detects and aligns the face.
        3. Generates and stores the 128-float embedding vector in the DB.
        """
        t_uuid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
        s_uuid = uuid.UUID(student_id) if isinstance(student_id, str) else student_id

        # Verify student exists and belongs to this tenant
        student_user = db.session.get(User, s_uuid)
        if not student_user or str(student_user.tenant_id) != str(t_uuid):
            raise ForbiddenException("Student does not belong to this tenant")

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
        
        # Save or update StudentProfile if roll_number is provided
        if roll_number:
            profile = StudentProfile.query.filter_by(student_id=s_uuid).first()
            if not profile:
                profile = StudentProfile(
                    tenant_id=t_uuid,
                    student_id=s_uuid,
                    roll_number=roll_number,
                    mobile_number=mobile_number,
                    department=department,
                    course=course,
                    semester_grade=semester_grade,
                    section=section
                )
                db.session.add(profile)
            else:
                profile.roll_number = roll_number
                profile.mobile_number = mobile_number
                profile.department = department
                profile.course = course
                profile.semester_grade = semester_grade
                profile.section = section

        # Check duplicate face registration (Anti-Proxy identity hijack prevention)
        existing_faces = StudentFace.query.filter_by(tenant_id=t_uuid, status="approved").all()
        if existing_faces:
            registered_ids = []
            registered_vecs = []
            for ef in existing_faces:
                if ef.student_id != s_uuid:
                    try:
                        dec_emb = AttendanceService.decrypt_embedding(ef.embedding)
                        registered_ids.append(ef.student_id)
                        registered_vecs.append(dec_emb)
                    except Exception:
                        pass
            
            if registered_vecs:
                best_idx, confidence = ai_engine.match_faces(embedding, registered_vecs)
                if best_idx != -1 and confidence >= 90.0:
                    matched_student = db.session.get(User, registered_ids[best_idx])
                    matched_name = f"{matched_student.first_name} {matched_student.last_name}" if matched_student else "Another Student"
                    raise ConflictException(f"Face is already registered to {matched_name}. Multi-account face reuse is prohibited.")

        # Encrypt the embedding before storing
        encrypted_embedding = AttendanceService.encrypt_embedding(embedding)

        # Set status based on app config
        auto_approve = current_app.config.get("AUTO_APPROVE_FACIAL_ENROLLMENT", True)
        status = "approved" if auto_approve else "pending_approval"

        # Save to database
        face_record = StudentFace(
            tenant_id=t_uuid,
            student_id=s_uuid,
            embedding=encrypted_embedding,
            image_quality_score=quality_score,
            status=status
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
            try:
                dec_emb = AttendanceService.decrypt_embedding(face.embedding)
                student_map[s_str]["embeddings"].append(dec_emb)
            except Exception:
                pass

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

            # Verify student exists and belongs to the session's tenant
            student_user = db.session.get(User, s_uuid)
            if not student_user or str(student_user.tenant_id) != str(session.tenant_id):
                raise ForbiddenException(f"Student {s_uuid} does not belong to this tenant")

            # Check duplicate database insertion
            existing = AttendanceRecord.query.filter_by(session_id=session.id, student_id=s_uuid).first()
            if existing:
                existing.status = status
                existing.verification_method = method
                existing.confidence_score = score
                existing.is_deleted = False
            else:
                new_record = AttendanceRecord(
                    tenant_id=session.tenant_id,
                    session_id=session.id,
                    student_id=s_uuid,
                    status=status,
                    verification_method=method,
                    confidence_score=score,
                    is_deleted=False
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
        record = AttendanceRecord.query.filter_by(id=r_uuid, is_deleted=False).first()
        if not record or record.student_id != s_uuid:
            raise NotFoundException("Attendance record not found")
        if str(record.tenant_id) != str(t_uuid):
            raise ForbiddenException("Tenant mismatch for correction request")

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
            
        # Verify reviewer belongs to same tenant
        reviewer = db.session.get(User, rev_uuid)
        if not reviewer or str(reviewer.tenant_id) != str(correction.tenant_id):
            raise ForbiddenException("Reviewer does not belong to the same tenant as the correction request")

        if correction.status != "pending":
            raise ConflictException("Correction request has already been reviewed")

        previous_status = correction.status
        correction.status = status
        correction.reviewed_by = rev_uuid
        correction.review_comments = comments
        if status == "approved":
            record = AttendanceRecord.query.filter_by(id=correction.record_id, is_deleted=False).first()
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

    @staticmethod
    def get_timetable(tenant_id: str, teacher_id: str):
        """
        Lists timetable slots for a teacher.
        """
        from backend.app.domains.academic.models import TimetableSlot, Subject, Section, Class, Course
        t_uuid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
        teach_uuid = uuid.UUID(teacher_id) if isinstance(teacher_id, str) else teacher_id

        slots = db.session.query(TimetableSlot, Subject, Section, Class, Course)\
            .join(Subject, TimetableSlot.subject_id == Subject.id)\
            .join(Section, TimetableSlot.section_id == Section.id)\
            .join(Class, Section.class_id == Class.id)\
            .join(Course, Class.course_id == Course.id)\
            .filter(TimetableSlot.tenant_id == t_uuid, TimetableSlot.teacher_id == teach_uuid).all()

        results = []
        for slot, subject, section, cls, course in slots:
            results.append({
                "id": str(slot.id),
                "day_of_week": slot.day_of_week,
                "start_time": slot.start_time.strftime("%H:%M") if slot.start_time else "",
                "end_time": slot.end_time.strftime("%H:%M") if slot.end_time else "",
                "room_number": slot.room_number,
                "subject": {
                    "id": str(subject.id),
                    "name": subject.name,
                    "code": subject.code
                },
                "section": {
                    "id": str(section.id),
                    "name": section.name
                },
                "class": {
                    "id": str(cls.id),
                    "name": cls.name
                },
                "course": {
                    "id": str(course.id),
                    "name": course.name
                }
            })
        return results

    @staticmethod
    def get_students_for_section(tenant_id: str, section_id: str = None):
        """
        Returns users with the role 'Student' in the given tenant and section.
        Also attaches their student profile and face enrollment status.
        """
        t_uuid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
        
        query = User.query.filter_by(tenant_id=t_uuid)
        users = query.all()
        
        results = []
        for user in users:
            is_student = False
            for role in user.roles:
                if role.name.lower() == "student":
                    is_student = True
                    break
            
            if not is_student:
                continue

            profile = StudentProfile.query.filter_by(student_id=user.id).first()
            if section_id and (not profile or str(profile.section) != str(section_id)):
                continue

            face = StudentFace.query.filter_by(student_id=user.id).first()
            
            results.append({
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_enrolled": face is not None,
                "profile": {
                    "roll_number": profile.roll_number if profile else "",
                    "mobile_number": profile.mobile_number if profile else "",
                    "department": profile.department if profile else "",
                    "course": profile.course if profile else "",
                    "semester_grade": profile.semester_grade if profile else "",
                    "section": profile.section if profile else "",
                    "profile_photo_url": profile.profile_photo_url if profile else ""
                } if profile else None
            })
        return results

    @staticmethod
    def get_sessions(tenant_id: str, user_id: str, is_teacher: bool):
        """
        Lists attendance sessions for a teacher or a student.
        """
        t_uuid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        
        if is_teacher:
            sessions = AttendanceSession.query.filter_by(tenant_id=t_uuid, teacher_id=user_uuid).order_by(AttendanceSession.date.desc()).all()
        else:
            records = AttendanceRecord.query.filter_by(tenant_id=t_uuid, student_id=user_uuid, is_deleted=False).all()
            session_ids = [r.session_id for r in records]
            if session_ids:
                sessions = AttendanceSession.query.filter(AttendanceSession.id.in_(session_ids)).order_by(AttendanceSession.date.desc()).all()
            else:
                sessions = []

        results = []
        for s in sessions:
            results.append({
                "id": str(s.id),
                "date": s.date.isoformat(),
                "start_time": s.start_time.isoformat() if s.start_time else "",
                "status": s.status,
                "gps_latitude": float(s.gps_latitude) if s.gps_latitude else None,
                "gps_longitude": float(s.gps_longitude) if s.gps_longitude else None,
                "gps_radius_meters": s.gps_radius_meters
            })
        return results

    @staticmethod
    def get_session_details(tenant_id: str, session_id: str):
        """
        Retrieves details of an attendance session and its corresponding records.
        """
        t_uuid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
        sess_uuid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id
        
        session = AttendanceSession.query.filter_by(tenant_id=t_uuid, id=sess_uuid).first()
        if not session:
            raise NotFoundException("Attendance session not found")

        records = AttendanceRecord.query.filter_by(session_id=session.id, is_deleted=False).all()
        records_list = []
        for r in records:
            student = db.session.get(User, r.student_id)
            profile = StudentProfile.query.filter_by(student_id=r.student_id).first()
            records_list.append({
                "record_id": str(r.id),
                "student_id": str(r.student_id),
                "student_name": f"{student.first_name} {student.last_name}" if student else "Unknown Student",
                "roll_number": profile.roll_number if profile else "",
                "status": r.status,
                "verification_method": r.verification_method,
                "confidence_score": r.confidence_score,
                "updated_at": r.updated_at.isoformat()
            })
            
        return {
            "session_id": str(session.id),
            "date": session.date.isoformat(),
            "status": session.status,
            "records": records_list
        }

    @staticmethod
    def get_corrections(tenant_id: str, user_id: str, is_teacher: bool):
        """
        Lists attendance correction requests.
        """
        t_uuid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        
        if is_teacher:
            corrections = AttendanceCorrection.query.filter_by(tenant_id=t_uuid).all()
        else:
            corrections = AttendanceCorrection.query.filter_by(tenant_id=t_uuid, student_id=user_uuid).all()
            
        results = []
        for c in corrections:
            student = db.session.get(User, c.student_id)
            record = AttendanceRecord.query.filter_by(id=c.record_id, is_deleted=False).first()
            session = db.session.get(AttendanceSession, record.session_id) if record else None
            
            results.append({
                "id": str(c.id),
                "student_id": str(c.student_id),
                "student_name": f"{student.first_name} {student.last_name}" if student else "Unknown",
                "record_id": str(c.record_id),
                "current_status": record.status if record else "unknown",
                "session_date": session.date.isoformat() if session else "",
                "requested_status": c.requested_status,
                "reason": c.reason,
                "evidence_url": c.evidence_url,
                "status": c.status,
                "review_comments": c.review_comments,
                "created_at": c.created_at.isoformat()
            })
        return results

    @staticmethod
    def approve_face(tenant_id: str, face_id: str, reviewer_id: str):
        """
        Approves a pending face registration and supersedes any previously active face
        registrations for the same student.
        """
        t_uuid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
        f_uuid = uuid.UUID(face_id) if isinstance(face_id, str) else face_id
        rev_uuid = uuid.UUID(reviewer_id) if isinstance(reviewer_id, str) else reviewer_id
        
        face = StudentFace.query.filter_by(tenant_id=t_uuid, id=f_uuid).first()
        if not face:
            raise NotFoundException("Face enrollment record not found")
            
        # Supersede previous active faces for this student
        previous_faces = StudentFace.query.filter_by(
            tenant_id=t_uuid, 
            student_id=face.student_id, 
            status="approved"
        ).all()
        for pf in previous_faces:
            if pf.id != face.id:
                pf.status = "superseded"
                
        face.status = "approved"
        face.approved_by = rev_uuid
        db.session.commit()
        return face
