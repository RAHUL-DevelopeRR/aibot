"""Script to reset viva sessions for testing - deletes in-progress sessions"""
import os
from dotenv import load_dotenv
load_dotenv()

from app import create_app
from extensions import db
from models.user import VivaSession, StudentAnswer

app = create_app()

with app.app_context():
    # Find in-progress sessions
    in_progress = VivaSession.query.filter_by(status='in_progress').all()
    print(f"Found {len(in_progress)} in-progress viva sessions")
    
    for session in in_progress:
        print(f"  - Session {session.id}: Student {session.student_id}, Experiment {session.experiment_id}")
        # Delete associated answers
        StudentAnswer.query.filter_by(viva_session_id=session.id).delete()
        db.session.delete(session)
    
    db.session.commit()
    print(f"\nDeleted {len(in_progress)} sessions. Students will get new questions on next attempt.")
