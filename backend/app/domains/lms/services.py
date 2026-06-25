import uuid
from datetime import datetime
from backend.app.core.database import db
from backend.app.domains.lms.models import Assignment, AssignmentVersion, AssignmentSubmission, StudyNote, StudyNoteVersion, StudyNoteBookmark
from backend.app.core.exceptions import NotFoundException, ConflictException, ForbiddenException

class LmsService:
    @staticmethod
    def create_note(tenant_id: str, subject_id: str, title: str, description: str, file_type: str, file_url: str, user_id: str):
        """
        Creates a new Study Note with Version 1.
        """
        t_id = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
        s_id = uuid.UUID(subject_id) if isinstance(subject_id, str) else subject_id
        u_id = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

        note = StudyNote(
            tenant_id=t_id,
            subject_id=s_id,
            title=title,
            description=description,
            file_type=file_type,
            created_by=u_id
        )
        db.session.add(note)
        db.session.flush()

        version = StudyNoteVersion(
            note_id=note.id,
            version=1,
            file_url=file_url,
            author_id=u_id,
            changes_summary="Initial upload"
        )
        db.session.add(version)
        db.session.commit()
        return note

    @staticmethod
    def update_note_version(note_id: str, file_url: str, changes_summary: str, user_id: str):
        """
        Creates a new version for an existing Study Note.
        """
        n_id = uuid.UUID(note_id) if isinstance(note_id, str) else note_id
        u_id = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

        note = db.session.get(StudyNote, n_id)
        if not note:
            raise NotFoundException("Study note not found")
            
        # Get latest version number
        latest_ver = db.session.query(db.func.max(StudyNoteVersion.version)).filter_by(note_id=note.id).scalar() or 0
        
        new_version = StudyNoteVersion(
            note_id=note.id,
            version=latest_ver + 1,
            file_url=file_url,
            author_id=u_id,
            changes_summary=changes_summary
        )
        db.session.add(new_version)
        db.session.commit()
        return new_version

    @staticmethod
    def list_notes(tenant_id: str, subject_id: str = None, search: str = None, user_id: str = None):
        """
        Lists notes with optional filters (subject, search term) and indicates if they are bookmarked.
        """
        t_id = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
        s_id = uuid.UUID(subject_id) if isinstance(subject_id, str) else subject_id if subject_id else None
        u_id = uuid.UUID(user_id) if isinstance(user_id, str) else user_id if user_id else None

        query = db.session.query(StudyNote).filter(StudyNote.tenant_id == t_id)
        
        if s_id:
            query = query.filter(StudyNote.subject_id == s_id)
        if search:
            query = query.filter(StudyNote.title.ilike(f"%{search}%") | StudyNote.description.ilike(f"%{search}%"))
            
        notes = query.all()
        
        # Resolve bookmarks if user_id is provided
        bookmarked_ids = set()
        if u_id:
            bookmarks = StudyNoteBookmark.query.filter_by(user_id=u_id).all()
            bookmarked_ids = {str(b.note_id) for b in bookmarks}

        res = []
        for note in notes:
            latest_version = db.session.query(StudyNoteVersion).filter_by(note_id=note.id).order_by(StudyNoteVersion.version.desc()).first()
            file_url = latest_version.file_url if latest_version else ""
            
            res.append({
                "id": str(note.id),
                "title": note.title,
                "description": note.description,
                "file_type": note.file_type,
                "file_url": file_url,
                "created_by": str(note.created_by),
                "created_at": note.created_at.isoformat(),
                "is_bookmarked": str(note.id) in bookmarked_ids
            })
        return res

    @staticmethod
    def toggle_bookmark(user_id: str, note_id: str):
        """
        Toggles bookmark status on a note.
        """
        u_id = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        n_id = uuid.UUID(note_id) if isinstance(note_id, str) else note_id

        note = db.session.get(StudyNote, n_id)
        if not note:
            raise NotFoundException("Study note not found")
            
        bookmark = StudyNoteBookmark.query.filter_by(user_id=u_id, note_id=n_id).first()
        if bookmark:
            db.session.delete(bookmark)
            db.session.commit()
            return False  # Bookmarked status is now False
        else:
            bookmark = StudyNoteBookmark(user_id=u_id, note_id=n_id)
            db.session.add(bookmark)
            db.session.commit()
            return True  # Bookmarked status is now True

    @staticmethod
    def create_assignment(tenant_id: str, subject_id: str, title: str, description: str, deadline_str: str, file_url: str, user_id: str):
        """
        Creates a new Assignment with Version 1.
        """
        t_id = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
        s_id = uuid.UUID(subject_id) if isinstance(subject_id, str) else subject_id
        u_id = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

        deadline = datetime.fromisoformat(deadline_str)
        assignment = Assignment(
            tenant_id=t_id,
            subject_id=s_id,
            title=title,
            description=description,
            deadline=deadline,
            created_by=u_id
        )
        db.session.add(assignment)
        db.session.flush()

        version = AssignmentVersion(
            assignment_id=assignment.id,
            version=1,
            file_url=file_url,
            author_id=u_id,
            changes_summary="Initial assignment publish"
        )
        db.session.add(version)
        db.session.commit()
        return assignment

    @staticmethod
    def submit_assignment(assignment_id: str, student_id: str, file_url: str):
        """
        Submits student response for an assignment. If submission already exists, updates it.
        """
        a_id = uuid.UUID(assignment_id) if isinstance(assignment_id, str) else assignment_id
        s_id = uuid.UUID(student_id) if isinstance(student_id, str) else student_id

        assignment = db.session.get(Assignment, a_id)
        if not assignment:
            raise NotFoundException("Assignment not found")
            
        if datetime.utcnow() > assignment.deadline:
            raise ConflictException("Assignment deadline has passed")

        submission = AssignmentSubmission.query.filter_by(assignment_id=a_id, student_id=s_id).first()
        if submission:
            submission.file_url = file_url
            submission.submitted_at = datetime.utcnow()
        else:
            submission = AssignmentSubmission(
                assignment_id=a_id,
                student_id=s_id,
                file_url=file_url
            )
            db.session.add(submission)
            
        db.session.commit()
        return submission

    @staticmethod
    def grade_submission(submission_id: str, grade: str, feedback: str, teacher_id: str):
        """
        Grades an assignment submission.
        """
        sub_id = uuid.UUID(submission_id) if isinstance(submission_id, str) else submission_id
        t_id = uuid.UUID(teacher_id) if isinstance(teacher_id, str) else teacher_id

        submission = db.session.get(AssignmentSubmission, sub_id)
        if not submission:
            raise NotFoundException("Submission not found")
            
        submission.grade = grade
        submission.feedback = feedback
        submission.graded_by = t_id
        submission.graded_at = datetime.utcnow()
        db.session.commit()
        return submission
