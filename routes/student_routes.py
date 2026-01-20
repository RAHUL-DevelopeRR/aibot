from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request
from flask_login import login_required, current_user
from datetime import datetime, date
from functools import wraps

from extensions import db
from models.user import VivaSession, VivaSchedule, StudentAnswer, LabConfig, Experiment, Subject
from services.gemini_service import get_gemini_service
from services.sheets_service import get_sheets_service

student_bp = Blueprint('student', __name__)


def student_required(f):
    """Decorator for student-only routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'student':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('auth.login')), 403
        return f(*args, **kwargs)
    return decorated_function


@student_bp.route('/dashboard')
@login_required
@student_required
def dashboard():
    """Student dashboard - shows labs and experiments with viva status"""
    # Get all lab subjects
    lab_subjects = Subject.query.filter_by(is_lab=True).all()
    
    # Get student's viva sessions
    my_sessions = (
        VivaSession.query
        .filter_by(student_id=current_user.id)
        .all()
    )
    session_by_exp = {s.experiment_id: s for s in my_sessions}
    
    # Build labs data with experiments and their status
    labs_data = []
    for subject in lab_subjects:
        for lab in subject.labs:
            lab_info = {
                'lab': lab,
                'subject': subject,
                'experiments': []
            }
            for exp in lab.experiments:
                # Get schedule for this experiment
                schedule = VivaSchedule.query.filter_by(experiment_id=exp.id).first()
                session = session_by_exp.get(exp.id)
                
                exp_info = {
                    'experiment': exp,
                    'schedule': schedule,
                    'session': session,
                    'status': 'not_scheduled'
                }
                
                if schedule:
                    if session:
                        exp_info['status'] = session.status
                    elif schedule.is_active_now():
                        exp_info['status'] = 'available'
                    elif schedule.scheduled_date > date.today():
                        exp_info['status'] = 'upcoming'
                    elif schedule.scheduled_date < date.today():
                        exp_info['status'] = 'expired'
                    else:
                        exp_info['status'] = 'today_not_active'
                
                lab_info['experiments'].append(exp_info)
            labs_data.append(lab_info)
    
    # Stats
    completed_sessions = [s for s in my_sessions if s.status in ['completed', 'violated']]
    total_completed = len(completed_sessions)
    total_marks = sum([s.obtained_marks or 0 for s in completed_sessions])
    max_marks = total_completed * 10
    average_percent = (total_marks / max_marks * 100) if max_marks > 0 else 0
    
    return render_template('student/dashboard.html',
                         labs_data=labs_data,
                         total_completed=total_completed,
                         total_marks=total_marks,
                         average_percent=round(average_percent, 1))


@student_bp.route('/viva/start/<int:experiment_id>')
@login_required
@student_required
def start_viva(experiment_id):
    """Start viva attempt - enforces scheduled time window"""
    experiment = Experiment.query.get_or_404(experiment_id)
    schedule = VivaSchedule.query.filter_by(experiment_id=experiment_id).first()
    
    if not schedule:
        flash('This experiment viva is not scheduled yet.', 'warning')
        return redirect(url_for('student.dashboard'))
    
    # ENFORCE: Check if schedule is active NOW
    if not schedule.is_active_now():
        today = date.today()
        if schedule.scheduled_date > today:
            flash(f'This viva is scheduled for {schedule.scheduled_date}. You cannot attempt it early.', 'warning')
        elif schedule.scheduled_date < today:
            flash('This viva schedule has expired.', 'danger')
        else:
            flash(f'This viva is only available between {schedule.start_time} and {schedule.end_time} today.', 'warning')
        return redirect(url_for('student.dashboard'))
    
    # Check for existing session
    existing_session = VivaSession.query.filter_by(
        student_id=current_user.id,
        experiment_id=experiment_id
    ).first()
    
    if existing_session:
        if existing_session.status in ['completed', 'violated']:
            flash('You have already completed this viva.', 'info')
            return redirect(url_for('student.view_marks', viva_id=existing_session.id))
        elif existing_session.status == 'in_progress':
            return redirect(url_for('student.attempt_viva', viva_session_id=existing_session.id))
    
    # Create new session
    viva_session = VivaSession(
        student_id=current_user.id,
        schedule_id=schedule.id,
        experiment_id=experiment_id,
        status='in_progress',
        total_marks=10,
        started_at=datetime.utcnow()
    )
    
    # Generate MCQ questions using Gemini
    gemini = get_gemini_service()
    if gemini:
        questions = gemini.generate_mcq_questions(
            experiment_title=experiment.title,
            experiment_description=experiment.description or '',
            materials_text=experiment.materials_text or experiment.lab_config.materials_text or '',
            lab_name=experiment.lab_config.lab_name,
            student_id=current_user.id,
            num_questions=10
        )
        viva_session.generated_questions = questions
    else:
        # Fallback: use empty questions (will show error in UI)
        viva_session.generated_questions = []
    
    schedule.enrolled_count += 1
    db.session.add(viva_session)
    db.session.commit()
    
    return redirect(url_for('student.attempt_viva', viva_session_id=viva_session.id))


@student_bp.route('/viva/attempt/<int:viva_session_id>')
@login_required
@student_required
def attempt_viva(viva_session_id):
    """Viva attempt interface - MCQ based"""
    viva = VivaSession.query.get_or_404(viva_session_id)
    
    if viva.student_id != current_user.id:
        flash('You do not have permission to access this viva.', 'danger')
        return redirect(url_for('student.dashboard'))
    
    if viva.status in ['completed', 'violated']:
        flash('This viva has already been completed.', 'info')
        return redirect(url_for('student.view_marks', viva_id=viva_session_id))
    
    # Check if schedule is still active
    if not viva.schedule.is_active_now():
        # Time window expired during attempt - finalize
        viva.finalize_violation('Time window expired')
        db.session.commit()
        flash('The viva time window has expired. Your answers have been submitted.', 'warning')
        return redirect(url_for('student.view_marks', viva_id=viva_session_id))
    
    experiment = viva.experiment
    questions = viva.generated_questions or []
    
    # Get already answered questions
    answered = (
        StudentAnswer.query
        .filter_by(viva_session_id=viva_session_id)
        .all()
    )
    answers_dict = {a.question_number: a.answer_text for a in answered}
    
    return render_template('student/viva_interface.html',
                         viva=viva,
                         experiment=experiment,
                         questions=questions,
                         answers_dict=answers_dict)


@student_bp.route('/viva/marks/<int:viva_id>')
@login_required
@student_required
def view_marks(viva_id):
    """View viva marks and feedback"""
    viva = VivaSession.query.get_or_404(viva_id)
    
    if viva.student_id != current_user.id:
        flash('You do not have permission to access this viva.', 'danger')
        return redirect(url_for('student.dashboard'))
    
    answers = (
        StudentAnswer.query
        .filter_by(viva_session_id=viva_id)
        .order_by(StudentAnswer.question_number)
        .all()
    )
    
    return render_template('student/view_marks.html',
                         viva=viva,
                         answers=answers)


@student_bp.route('/available-vivaes')
@login_required
@student_required
def available_vivaes():
    """Show available vivaes - redirects to dashboard which shows all experiments"""
    return redirect(url_for('student.dashboard'))


@student_bp.route('/enroll/<int:schedule_id>')
@login_required
@student_required
def enroll_viva(schedule_id):
    """Enroll in a viva schedule"""
    schedule = VivaSchedule.query.get_or_404(schedule_id)
    
    existing = VivaSession.query.filter_by(
        student_id=current_user.id,
        lab_config_id=schedule.lab_config_id
    ).first()
    
    if existing:
        flash('You are already enrolled in this lab viva.', 'warning')
        return redirect(url_for('student.dashboard'))
    
    if schedule.enrolled_count >= schedule.total_slots:
        flash('This viva schedule is full.', 'danger')
        return redirect(url_for('student.available_vivaes'))
    
    viva_session = VivaSession(
        student_id=current_user.id,
        schedule_id=schedule_id,
        lab_config_id=schedule.lab_config_id,
        status='scheduled',
        total_marks=schedule.lab_config.total_marks
    )
    
    schedule.enrolled_count += 1
    
    db.session.add(viva_session)
    db.session.commit()
    
    flash('Successfully enrolled in the viva!', 'success')
    return redirect(url_for('student.dashboard'))
