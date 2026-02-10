from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from functools import wraps

# IST timezone offset (UTC+05:30)
IST_OFFSET = timedelta(hours=5, minutes=30)

def get_ist_today():
    """Get current date in IST"""
    return (datetime.utcnow() + IST_OFFSET).date()

from extensions import db
from models.user import VivaSchedule, VivaSession, Subject, LabConfig, User, Experiment, TeacherSubject, StudentAnswer
from services.sheets_service import get_sheets_service
from services.sync_service import sync_experiments_from_sheets, sync_teachers_from_sheets, cleanup_old_experiments

teacher_bp = Blueprint('teacher', __name__)


def teacher_required(f):
    """Decorator for teacher-only routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'teacher':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('auth.login')), 403
        return f(*args, **kwargs)
    return decorated_function


@teacher_bp.route('/dashboard')
@login_required
@teacher_required
def dashboard():
    """Teacher dashboard - shows labs, experiments, schedules and student marks"""
    
    # Auto-sync from Google Sheets if no experiments exist
    total_experiments = Experiment.query.count()
    if total_experiments == 0:
        result = sync_experiments_from_sheets()
        if result['success']:
            flash(f"Auto-synced: {result['message']}", 'success')
        else:
            flash(f"No experiments found. Click 'Sync from Sheets' to load experiments from Google Sheets.", 'info')
    
    # Get teacher's scheduled vivaes
    schedules = (
        VivaSchedule.query
        .filter_by(teacher_id=current_user.id)
        .order_by(VivaSchedule.scheduled_date.desc())
        .all()
    )
    
    # Get all students from Google Sheets (Single Source of Truth)
    sheets = get_sheets_service()
    students_from_sheets = []
    if sheets:
        students_from_sheets = sheets.get_all_students_with_marks()
    
    # Fallback to local DB for registered students (for other purposes)
    students = User.query.filter_by(role='student').all()
    
    # Get teacher's subjects (if assigned)
    teacher_subjects = TeacherSubject.query.filter_by(teacher_id=current_user.id).all()
    my_subject_ids = [ts.subject_id for ts in teacher_subjects]
    
    # Get all lab subjects (or only teacher's if assigned)
    if my_subject_ids:
        lab_subjects = Subject.query.filter(Subject.id.in_(my_subject_ids), Subject.is_lab == True).all()
    else:
        lab_subjects = Subject.query.filter_by(is_lab=True).all()
    
    # Build labs data with experiments
    labs_data = []
    for subject in lab_subjects:
        for lab in subject.labs:
            lab_info = {
                'lab': lab,
                'subject': subject,
                'experiments': []
            }
            for exp in lab.experiments:
                schedule = VivaSchedule.query.filter_by(experiment_id=exp.id).first()
                sessions = VivaSession.query.filter_by(experiment_id=exp.id).all()
                completed = [s for s in sessions if s.status in ['completed', 'violated']]
                
                lab_info['experiments'].append({
                    'experiment': exp,
                    'schedule': schedule,
                    'total_students': len(sessions),
                    'completed_count': len(completed),
                    'avg_marks': sum(s.obtained_marks or 0 for s in completed) / len(completed) if completed else 0
                })
            labs_data.append(lab_info)
    
    # Stats (using IST timezone)
    total_schedules = len(schedules)
    today_ist = get_ist_today()
    today_schedules = len([s for s in schedules if s.scheduled_date == today_ist])
    # Use Google Sheets count as Single Source of Truth
    total_students = len(students_from_sheets) if students_from_sheets else len(students)
    
    return render_template('teacher/dashboard.html',
                         schedules=schedules,
                         labs_data=labs_data,
                         students=students,
                         total_schedules=total_schedules,
                         today_schedules=today_schedules,
                         total_students=total_students)


@teacher_bp.route('/labs')
@login_required
@teacher_required
def view_labs():
    """View all labs"""
    subjects = Subject.query.all()
    
    for subject in subjects:
        subject.labs = LabConfig.query.filter_by(subject_id=subject.id).all()
    
    return render_template('teacher/view_labs.html', subjects=subjects)


@teacher_bp.route('/schedule-viva', methods=['GET', 'POST'])
@login_required
@teacher_required
def schedule_viva():
    """Schedule a viva for a specific experiment"""
    if request.method == 'POST':
        experiment_id = request.form.get('experiment_id', type=int)
        scheduled_date = request.form.get('scheduled_date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        total_slots = request.form.get('total_slots', 50, type=int)
        
        if not all([experiment_id, scheduled_date, start_time, end_time]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('teacher.schedule_viva'))
        
        # Check if experiment already has a schedule
        existing = VivaSchedule.query.filter_by(experiment_id=experiment_id).first()
        if existing:
            flash('This experiment already has a scheduled viva. Delete it first to reschedule.', 'warning')
            return redirect(url_for('teacher.schedule_viva'))
        
        try:
            scheduled_dt = datetime.strptime(f"{scheduled_date} {start_time}", "%Y-%m-%d %H:%M")
            end_dt = datetime.strptime(f"{scheduled_date} {end_time}", "%Y-%m-%d %H:%M")
            
            if scheduled_dt >= end_dt:
                flash('Start time must be before end time.', 'danger')
                return redirect(url_for('teacher.schedule_viva'))
            
            if scheduled_dt < datetime.utcnow():
                flash('Cannot schedule viva in the past.', 'danger')
                return redirect(url_for('teacher.schedule_viva'))
            
            # Convert string date to date object for SQLite
            scheduled_date_obj = datetime.strptime(scheduled_date, "%Y-%m-%d").date()
            
            schedule = VivaSchedule(
                teacher_id=current_user.id,
                experiment_id=experiment_id,
                scheduled_date=scheduled_date_obj,
                start_time=start_time,
                end_time=end_time,
                total_slots=total_slots,
                status='scheduled'
            )
            
            db.session.add(schedule)
            db.session.commit()
            
            flash('Viva scheduled successfully!', 'success')
            return redirect(url_for('teacher.view_schedule', schedule_id=schedule.id))
        
        except ValueError:
            flash('Invalid date or time format.', 'danger')
    
    # Get all experiments grouped by lab
    labs = LabConfig.query.all()
    experiments_by_lab = {}
    for lab in labs:
        experiments_by_lab[lab.id] = {
            'lab': lab,
            'experiments': Experiment.query.filter_by(lab_config_id=lab.id).order_by(Experiment.experiment_no).all()
        }
    
    selected_experiment_id = request.args.get('experiment_id', type=int)
    
    return render_template('teacher/schedule_viva.html', 
                         labs=labs, 
                         experiments_by_lab=experiments_by_lab,
                         now=datetime.now(),
                         selected_experiment_id=selected_experiment_id)


@teacher_bp.route('/schedule/<int:schedule_id>')
@login_required
@teacher_required
def view_schedule(schedule_id):
    """View schedule details"""
    schedule = VivaSchedule.query.get_or_404(schedule_id)
    
    if schedule.teacher_id != current_user.id:
        flash('You do not have permission to access this schedule.', 'danger')
        return redirect(url_for('teacher.dashboard'))
    
    viva_sessions = (
        VivaSession.query
        .filter_by(schedule_id=schedule_id)
        .all()
    )
    
    return render_template('teacher/view_schedule.html',
                         schedule=schedule,
                         viva_sessions=viva_sessions)


@teacher_bp.route('/results/<int:lab_id>')
@login_required
@teacher_required
def view_results(lab_id):
    """View lab results - shows all experiments and student marks"""
    lab_config = LabConfig.query.get_or_404(lab_id)
    
    # Build results by experiment
    experiments_data = []
    for exp in lab_config.experiments:
        sessions = (
            VivaSession.query
            .filter_by(experiment_id=exp.id)
            .all()
        )
        
        students_data = []
        for session in sessions:
            student = User.query.get(session.student_id)
            students_data.append({
                'student': student,
                'session': session,
                'marks': session.obtained_marks or 0,
                'status': session.status
            })
        
        completed = [s for s in sessions if s.status in ['completed', 'violated']]
        avg_marks = sum(s.obtained_marks or 0 for s in completed) / len(completed) if completed else 0
        
        experiments_data.append({
            'experiment': exp,
            'students': students_data,
            'total_attempted': len(sessions),
            'completed_count': len(completed),
            'avg_marks': round(avg_marks, 1)
        })
    
    return render_template('teacher/view_results.html',
                         lab_config=lab_config,
                         experiments_data=experiments_data)


@teacher_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@teacher_required
def profile():
    """Teacher profile - name, designation, subjects"""
    if request.method == 'POST':
        current_user.name = request.form.get('name', current_user.name)
        current_user.designation = request.form.get('designation')
        current_user.department = request.form.get('department')
        years = request.form.getlist('years')
        current_user.years_handling = years
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('teacher.profile'))
    
    # Get assigned subjects
    teacher_subjects = TeacherSubject.query.filter_by(teacher_id=current_user.id).all()
    all_subjects = Subject.query.all()
    
    return render_template('teacher/profile.html',
                         teacher_subjects=teacher_subjects,
                         all_subjects=all_subjects)


@teacher_bp.route('/students')
@login_required
@teacher_required
def view_students():
    """View all students and their viva marks - Data from Google Sheets"""
    sheets = get_sheets_service()
    
    if not sheets:
        flash('Google Sheets not configured. Cannot fetch student data.', 'danger')
        return redirect(url_for('teacher.dashboard'))
    
    # Fetch students with marks directly from Google Sheets (Single Source of Truth)
    students_from_sheets = sheets.get_all_students_with_marks()
    
    # Get labs for display context
    labs = LabConfig.query.all()
    
    # Build student data for template
    students_data = []
    for student in students_from_sheets:
        student_info = {
            'reg_no': student['reg_no'],
            'name': student['name'],
            'experiments': student['experiments'],  # Dict: {1: marks, 2: marks, ...}
            'total_marks': sum(m for m in student['experiments'].values() if m is not None)
        }
        students_data.append(student_info)
    
    return render_template('teacher/view_students.html',
                         students_data=students_data,
                         labs=labs)


@teacher_bp.route('/export-marks/<int:lab_id>')
@login_required
@teacher_required
def export_marks(lab_id):
    """Export lab marks to Google Sheets"""
    sheets = get_sheets_service()
    if not sheets:
        flash('Google Sheets is not configured. Set GOOGLE_SHEETS_CREDENTIALS_PATH and GOOGLE_SHEET_ID environment variables.', 'warning')
        return redirect(url_for('teacher.view_results', lab_id=lab_id))
    
    success = sheets.export_all_marks(lab_id)
    if success:
        flash('Marks exported to Google Sheets successfully!', 'success')
    else:
        flash('Failed to export marks. Check server logs.', 'danger')
    
    return redirect(url_for('teacher.view_results', lab_id=lab_id))


@teacher_bp.route('/sync-from-sheets')
@login_required
@teacher_required
def sync_from_sheets():
    """Sync experiments and labs from Google Sheets"""
    result = sync_experiments_from_sheets()
    
    if result['success']:
        flash(result['message'], 'success')
    else:
        flash(result['message'], 'danger')
    
    return redirect(url_for('teacher.dashboard'))


@teacher_bp.route('/clean-and-sync')
@login_required
@teacher_required
def clean_and_sync():
    """Clean all existing experiments and sync fresh from Google Sheets"""
    # First clean old data
    cleanup_result = cleanup_old_experiments()
    if not cleanup_result['success']:
        flash(f"Cleanup failed: {cleanup_result['message']}", 'danger')
        return redirect(url_for('teacher.dashboard'))
    
    flash(f"Cleaned: {cleanup_result['message']}", 'info')
    
    # Then sync from sheets
    result = sync_experiments_from_sheets()
    
    if result['success']:
        flash(result['message'], 'success')
    else:
        flash(result['message'], 'danger')
    
    return redirect(url_for('teacher.dashboard'))
