"""
Viva Routes - Secure MCQ Examination Endpoints
Implements the secure viva flow with fullscreen exam window.
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps
import uuid
from datetime import datetime

from extensions import db
from models.user import VivaSession, VivaSchedule, Experiment
from services.viva_service import (
    build_response,
    generate_mcq_with_perplexity,
    store_session_questions,
    get_session_questions,
    clear_session,
    calculate_score
)
from services.sheets_service import get_sheets_service

viva_bp = Blueprint('viva', __name__)


def student_required(f):
    """Decorator for student-only routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'student':
            if request.path.startswith('/viva/api/'):
                return jsonify({'error': 'Unauthorized - Student access required'}), 403
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@viva_bp.route('/secure-exam/<int:experiment_id>')
@login_required
@student_required
def secure_exam(experiment_id):
    """
    Render the secure exam page for an experiment.
    This opens in a new window with fullscreen security measures.
    """
    experiment = Experiment.query.get_or_404(experiment_id)
    schedule = VivaSchedule.query.filter_by(experiment_id=experiment_id).first()
    
    if not schedule:
        return render_template('errors/403.html', message='Viva not scheduled for this experiment'), 403
    
    # Check if schedule is active
    if not schedule.is_active_now():
        return render_template('errors/403.html', message='Viva is not currently active. Please check the schedule.'), 403
    
    # Check for existing completed session
    existing_session = VivaSession.query.filter_by(
        student_id=current_user.id,
        experiment_id=experiment_id
    ).first()
    
    if existing_session and existing_session.status in ['completed', 'violated']:
        return redirect(url_for('student.view_marks', viva_id=existing_session.id))
    
    # Create or get viva session
    if not existing_session:
        existing_session = VivaSession(
            student_id=current_user.id,
            schedule_id=schedule.id,
            experiment_id=experiment_id,
            status='in_progress',
            total_marks=10,
            started_at=datetime.utcnow()
        )
        schedule.enrolled_count += 1
        db.session.add(existing_session)
        db.session.commit()
    
    # Generate a stable session ID for this exam attempt
    student_session = f"{current_user.id}-{experiment_id}-{existing_session.id}"
    
    # Build experiment data for template
    experiment_data = {
        'id': experiment.id,
        'number': experiment.experiment_no,
        'name': experiment.title,
        'mcq_topic': experiment.title  # Use title as topic, can add dedicated field later
    }
    
    return render_template(
        'viva/secure_exam.html',
        experiment=experiment_data,
        student_session=student_session,
        student_reg_no=current_user.roll_number,
        viva_session_id=existing_session.id
    )


@viva_bp.route('/api/experiments', methods=['GET'])
@login_required
@student_required
def get_experiments():
    """API endpoint to fetch available experiments for the student."""
    try:
        # Get experiments from database (scheduled ones)
        from models.user import Subject, LabConfig
        
        lab_subjects = Subject.query.filter_by(is_lab=True).all()
        experiments_list = []
        
        for subject in lab_subjects:
            for lab in subject.labs:
                for exp in lab.experiments:
                    schedule = VivaSchedule.query.filter_by(experiment_id=exp.id).first()
                    if schedule and schedule.is_active_now():
                        experiments_list.append({
                            'id': exp.id,
                            'number': exp.experiment_no,
                            'name': exp.title,
                            'mcq_topic': exp.title,
                            'lab_name': lab.lab_name
                        })
        
        return jsonify(build_response(
            "success",
            "mcqs_ready",
            data={"experiments": experiments_list},
            message="Experiments loaded"
        ))
        
    except Exception as e:
        print(f"[VivaRoutes] Error fetching experiments: {e}")
        return jsonify(build_response("error", "error", message=str(e))), 500


@viva_bp.route('/api/generate', methods=['POST'])
@login_required
@student_required
def generate_mcq():
    """
    API endpoint to generate MCQs for an experiment.
    Uses Perplexity API for dynamic question generation.
    """
    try:
        data = request.get_json()
        topic = data.get('topic', 'General Knowledge')
        experiment_id = data.get('experiment_id')
        student_session = data.get('student_session', str(uuid.uuid4()))
        num_questions = 10  # Fixed to 10 questions
        
        # If experiment_id is provided, fetch the topic from the experiment
        if experiment_id:
            experiment = Experiment.query.get(int(experiment_id))
            if experiment:
                topic = experiment.title
        
        # Generate a unique session ID combining student session and experiment
        unique_session = f"{student_session}-{experiment_id or 'manual'}-{uuid.uuid4()}"
        
        # Generate MCQs with uniqueness
        result = generate_mcq_with_perplexity(topic, num_questions, 'medium', unique_session)
        
        if 'error' in result:
            return jsonify(build_response("error", "error", message=result["error"])), 500
        
        questions = result.get('questions', [])
        if not questions:
            return jsonify(build_response("error", "error", message="No questions generated")), 500
        
        # Store questions in session for later scoring
        session_key = f"{student_session}:{experiment_id or 'manual'}"
        store_session_questions(session_key, questions, topic)
        
        # Return questions to frontend (without correct answers exposed prominently)
        # The correct_answer is needed for client-side immediate feedback, but scoring is server-side
        return jsonify(build_response(
            "success",
            "mcqs_ready",
            data={"questions": questions},
            message="MCQs generated"
        ))
        
    except Exception as e:
        print(f"[VivaRoutes] Error generating MCQs: {e}")
        return jsonify(build_response("error", "error", message=str(e))), 500


@viva_bp.route('/api/save-marks', methods=['POST'])
@login_required
@student_required
def save_marks():
    """
    API endpoint to save student marks to Google Sheets.
    Calculates score from stored questions and submitted answers.
    """
    try:
        data = request.get_json()
        
        # Extract required fields
        experiment_name = data.get('experiment_name', 'Unknown')
        experiment_id = data.get('experiment_id', 0)
        answers = data.get('answers', {}) or {}
        session_id = data.get('session_id', '')
        viva_session_id = data.get('viva_session_id')
        client_score = data.get('score')  # Pre-calculated score from client (for termination)
        
        # Use logged-in user's roll number (NOT hardcoded)
        student_id = current_user.roll_number
        
        # Get stored questions for scoring
        session_key = f"{session_id}:{experiment_id or 'manual'}"
        stored_questions = get_session_questions(session_key)
        questions = stored_questions or data.get('questions', [])
        
        # Use client score if provided (e.g., session terminated with score=0)
        # Otherwise calculate from answers
        if client_score is not None:
            score = int(client_score)
            total = 10  # Default total
            print(f"[VivaRoutes] Using client-provided score: {score}")
        elif questions:
            # Calculate score from answers
            score_result = calculate_score(questions, answers)
            score = score_result['score']
            total = score_result['total']
        else:
            # No questions and no client score - error
            return jsonify(build_response(
                "error",
                "error",
                message="No questions available for scoring"
            )), 400
        
        print(f"[VivaRoutes] Saving marks: Student={student_id}, Exp={experiment_name}, Score={score}/{total}")
        
        # Update VivaSession in database
        if viva_session_id:
            viva = VivaSession.query.get(viva_session_id)
            if viva and viva.student_id == current_user.id:
                viva.obtained_marks = score
                viva.status = 'completed'
                viva.completed_at = datetime.utcnow()
                db.session.commit()
        
        # Save to Google Sheets using cell-level update
        sheets = get_sheets_service()
        saved = False
        
        if sheets and student_id:
            try:
                # Use update_student_experiment_mark for cell-level update
                saved = sheets.update_student_experiment_mark(
                    reg_no=student_id,
                    experiment_no=int(experiment_id) if experiment_id else 1,
                    marks=score
                )
                if saved:
                    print(f"[VivaRoutes] Marks saved to Google Sheets: {student_id} Exp_{experiment_id} = {score}")
            except Exception as sheet_error:
                print(f"[VivaRoutes] Google Sheets error: {sheet_error}")
        
        # Clear session store
        clear_session(session_key)
        
        message = "Marks saved to Google Sheets" if saved else "Score computed, but failed to save to Sheets"
        
        return jsonify(build_response(
            "success",
            "exam_completed",
            data={
                "score": score,
                "total": total,
                "saved": saved
            },
            message=message
        ))
        
    except Exception as e:
        print(f"[VivaRoutes] Error saving marks: {e}")
        return jsonify(build_response("error", "error", message=str(e))), 500


@viva_bp.route('/api/violation', methods=['POST'])
@login_required
@student_required
def report_violation():
    """Report anti-cheat violation - finalizes viva with 0 marks."""
    try:
        data = request.get_json() or {}
        viva_session_id = data.get('viva_session_id')
        reason = data.get('reason', 'Tab switch or window blur detected')
        
        if viva_session_id:
            viva = VivaSession.query.get(viva_session_id)
            if viva and viva.student_id == current_user.id:
                if viva.status not in ['completed', 'violated']:
                    viva.violation_count = (viva.violation_count or 0) + 1
                    viva.finalize_violation(reason)
                    db.session.commit()
                    
                    # Write 0 marks to Google Sheets
                    sheets = get_sheets_service()
                    if sheets and viva.experiment:
                        try:
                            sheets.update_student_experiment_mark(
                                reg_no=current_user.roll_number,
                                experiment_no=viva.experiment.experiment_no,
                                marks=0
                            )
                        except Exception as sheet_error:
                            print(f"[VivaRoutes] Google Sheets error: {sheet_error}")
        
        return jsonify({
            'success': True,
            'message': 'Violation recorded. Viva finalized with 0 marks.',
            'violation_reason': reason
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
