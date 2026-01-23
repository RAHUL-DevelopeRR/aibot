# Lab Viva Assistant - Complete Project Documentation

> **AI-Powered Lab Viva Examination System** with secure anti-cheat features, MCQ generation via Perplexity AI, and Google Sheets integration.

---

## 📁 Project Structure

```
aibot/
├── 📄 app.py                    # Flask application factory
├── 📄 config.py                 # Configuration classes
├── 📄 extensions.py             # Flask extensions (SQLAlchemy, Login, CSRF)
├── 📄 seed_data.py              # Database seeding script
├── 📄 requirements.txt          # Python dependencies
├── 📄 Procfile                  # Deployment config
├── 📄 credentials.json          # Google Sheets service account
├── 📄 .env                      # Environment variables
│
├── 📂 models/
│   ├── __init__.py
│   └── user.py                  # User, Subject, Lab, Experiment, VivaSession models
│
├── 📂 routes/
│   ├── auth_routes.py           # Login, Register, Logout
│   ├── student_routes.py        # Student dashboard, viva attempts
│   ├── teacher_routes.py        # Teacher dashboard, scheduling
│   ├── api_routes.py            # RESTful API for viva operations
│   └── chatbot_routes.py        # AI chatbot endpoints
│
├── 📂 services/
│   ├── perplexity_service.py    # Perplexity AI for MCQ generation
│   ├── sheets_service.py        # Google Sheets integration
│   ├── sync_service.py          # Data sync from Sheets to DB
│   └── gemini_service.py        # Gemini AI (optional MCQ generator)
│
├── 📂 static/
│   ├── 📂 css/
│   │   └── style.css            # Global styles
│   └── 📂 js/
│       ├── anticheat.js         # Anti-cheat security module
│       ├── chatbot.js           # Floating chatbot widget
│       └── security.js          # General security utilities
│
└── 📂 templates/
    ├── base.html                # Base template with navbar/footer
    ├── 📂 auth/
    │   ├── login.html
    │   └── register.html
    ├── 📂 student/
    │   ├── dashboard.html
    │   ├── viva_interface.html
    │   └── view_marks.html
    ├── 📂 teacher/
    │   ├── dashboard.html
    │   ├── schedule_viva.html
    │   ├── view_labs.html
    │   └── view_students.html
    └── 📂 errors/
        ├── 403.html, 404.html, 500.html
```

---

## 🐍 Python Source Code

### `app.py` - Application Factory

```python
from dotenv import load_dotenv
load_dotenv()  # Load .env file before anything else

from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_login import current_user
from flask_wtf.csrf import generate_csrf
from config import config
from extensions import db, login_manager, csrf
from flask_wtf.csrf import CSRFError
from datetime import timedelta
import os

# IST offset (UTC+05:30)
IST_OFFSET = timedelta(hours=5, minutes=30)


def create_app(config_name='development'):
    """Application factory"""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # Custom unauthorized handler - returns JSON for API routes
    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Unauthorized - Please log in', 'login_required': True}), 401
        return redirect(url_for('auth.login'))
    
    # User loader
    @login_manager.user_loader
    def load_user(user_id):
        from models.user import User
        return User.query.get(int(user_id))
    
    # Register blueprints
    from routes.auth_routes import auth_bp
    from routes.student_routes import student_bp
    from routes.teacher_routes import teacher_bp
    from routes.api_routes import api_bp
    from routes.chatbot_routes import chatbot_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(teacher_bp, url_prefix='/teacher')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(chatbot_bp, url_prefix='/chatbot')
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Resource not found'}), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(403)
    def forbidden(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Forbidden'}), 403
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'CSRF token missing or invalid', 'csrf_error': True}), 400
        return render_template('errors/403.html'), 403
    
    # Home route
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            if current_user.role == 'student':
                return redirect(url_for('student.dashboard'))
            if current_user.role == 'teacher':
                return redirect(url_for('teacher.dashboard'))
        return redirect(url_for('auth.login'))

    # Make csrf_token available in templates
    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token=generate_csrf)

    # Add custom Jinja2 filter for UTC to IST conversion
    @app.template_filter('to_ist')
    def to_ist_filter(dt):
        if dt is None:
            return None
        return dt + IST_OFFSET

    return app


# Create app instance for WSGI servers
app = create_app(os.environ.get('FLASK_ENV', 'development'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
```

---

### `config.py` - Configuration

```python
import os
from datetime import timedelta

class Config:
    """Base configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_TIME_LIMIT = None
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SEND_FILE_MAX_AGE_DEFAULT = 31536000


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI', 'sqlite:///app.db')
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    _db_url = os.getenv('DATABASE_URL') or os.getenv('SQLALCHEMY_DATABASE_URI', 'sqlite:///app.db')
    if _db_url and _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SESSION_COOKIE_SECURE = True
    SQLALCHEMY_ECHO = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
```

---

### `extensions.py` - Flask Extensions

```python
"""Flask extensions - centralized to avoid circular imports"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
```

---

### `models/user.py` - Database Models

```python
from extensions import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json


class User(UserMixin, db.Model):
    """User model for students and teachers"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    roll_number = db.Column(db.String(50), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # 'student' or 'teacher'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Teacher profile fields
    designation = db.Column(db.String(100))
    department = db.Column(db.String(100))
    years_handling = db.Column(db.JSON, default=[])
    
    # Relationships
    viva_sessions = db.relationship('VivaSession', backref='student', lazy=True, foreign_keys='VivaSession.student_id')
    schedules = db.relationship('VivaSchedule', backref='teacher', lazy=True, foreign_keys='VivaSchedule.teacher_id')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Subject(db.Model):
    """Subject model"""
    __tablename__ = 'subjects'
    
    id = db.Column(db.Integer, primary_key=True)
    subject_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    subject_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    is_lab = db.Column(db.Boolean, default=False)
    year = db.Column(db.String(10))
    
    labs = db.relationship('LabConfig', backref='subject', lazy=True, cascade='all, delete-orphan')


class LabConfig(db.Model):
    """Lab configuration model"""
    __tablename__ = 'lab_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    lab_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    total_experiments = db.Column(db.Integer, default=10)
    materials_text = db.Column(db.Text)
    
    experiments = db.relationship('Experiment', backref='lab_config', lazy=True, cascade='all, delete-orphan')


class Experiment(db.Model):
    """Experiment model - 10 experiments per lab"""
    __tablename__ = 'experiments'
    
    id = db.Column(db.Integer, primary_key=True)
    lab_config_id = db.Column(db.Integer, db.ForeignKey('lab_configs.id'), nullable=False)
    experiment_no = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    total_marks = db.Column(db.Integer, default=10)
    duration_minutes = db.Column(db.Integer, default=15)
    
    schedules = db.relationship('VivaSchedule', backref='experiment', lazy=True, cascade='all, delete-orphan')
    viva_sessions = db.relationship('VivaSession', backref='experiment', lazy=True, cascade='all, delete-orphan')


class VivaSchedule(db.Model):
    """Viva schedule model - per experiment"""
    __tablename__ = 'viva_schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    experiment_id = db.Column(db.Integer, db.ForeignKey('experiments.id'), nullable=False)
    scheduled_date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.String(5), nullable=False)  # HH:MM
    end_time = db.Column(db.String(5), nullable=False)
    total_slots = db.Column(db.Integer, default=50)
    enrolled_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='scheduled')
    
    viva_sessions = db.relationship('VivaSession', backref='schedule', lazy=True, cascade='all, delete-orphan')
    
    def is_active_now(self):
        """Check if schedule is currently active (within time window)"""
        from datetime import date, time, timedelta
        IST_OFFSET = timedelta(hours=5, minutes=30)
        now_utc = datetime.utcnow()
        now_ist = now_utc + IST_OFFSET
        
        today = now_ist.date()
        current_time = now_ist.time()
        
        if self.scheduled_date != today:
            return False
        
        start = datetime.strptime(self.start_time, '%H:%M').time()
        end = datetime.strptime(self.end_time, '%H:%M').time()
        
        return start <= current_time <= end


class VivaSession(db.Model):
    """Viva session model - per student per experiment"""
    __tablename__ = 'viva_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    schedule_id = db.Column(db.Integer, db.ForeignKey('viva_schedules.id'), nullable=False)
    experiment_id = db.Column(db.Integer, db.ForeignKey('experiments.id'), nullable=False)
    status = db.Column(db.String(20), default='scheduled')  # scheduled, in_progress, completed, violated
    total_marks = db.Column(db.Integer, default=10)
    obtained_marks = db.Column(db.Integer, default=0)
    
    # MCQ questions generated for this student
    generated_questions = db.Column(db.JSON, default=[])
    
    # Anti-cheat violation tracking
    violation_detected = db.Column(db.Boolean, default=False)
    violation_reason = db.Column(db.String(255))
    violation_count = db.Column(db.Integer, default=0)
    
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    answers = db.relationship('StudentAnswer', backref='viva_session', lazy=True, cascade='all, delete-orphan')
    
    def finalize_violation(self, reason):
        """Finalize session with 0 marks due to violation"""
        self.violation_detected = True
        self.violation_reason = reason
        self.obtained_marks = 0
        self.status = 'violated'
        self.completed_at = datetime.utcnow()


class StudentAnswer(db.Model):
    """Student answer model"""
    __tablename__ = 'student_answers'
    
    id = db.Column(db.Integer, primary_key=True)
    viva_session_id = db.Column(db.Integer, db.ForeignKey('viva_sessions.id'), nullable=False)
    question_number = db.Column(db.Integer, nullable=False)
    answer_text = db.Column(db.Text)
    marks_obtained = db.Column(db.Integer)
    teacher_feedback = db.Column(db.Text)
    
    __table_args__ = (
        db.UniqueConstraint('viva_session_id', 'question_number', name='unique_answer'),
    )
```

---

### `routes/auth_routes.py` - Authentication

```python
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from extensions import db
from models.user import User
from services.sheets_service import get_sheets_service

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        if current_user.role == 'student':
            return redirect(url_for('student.dashboard'))
        else:
            return redirect(url_for('teacher.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', '').strip()
        
        if not all([email, password, role]):
            flash('Email, password, and role are required.', 'danger')
            return redirect(url_for('auth.login'))
        
        user = User.query.filter_by(email=email, role=role).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('student.dashboard') if user.role == 'student' else url_for('teacher.dashboard'))
        else:
            flash('Invalid email, password, or role.', 'danger')
    
    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('student.dashboard') if current_user.role == 'student' else url_for('teacher.dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        roll_number = request.form.get('roll_number', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        role = request.form.get('role', '').strip()
        
        # Validation
        if not all([name, email, roll_number, password, role]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('auth.register'))
        
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return redirect(url_for('auth.register'))
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('auth.register'))
        
        # For students: Validate Reg_No exists in Google Sheets
        if role == 'student':
            sheets = get_sheets_service()
            if sheets:
                student_data = sheets.validate_student_reg_no(roll_number)
                if not student_data:
                    flash('Registration Number not found in student records.', 'danger')
                    return redirect(url_for('auth.register'))
                if student_data.get('name'):
                    name = student_data['name']
        
        # Create user
        user = User(
            name=name,
            email=email,
            roll_number=roll_number.strip().upper(),
            role=role
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')


@auth_bp.route('/logout')
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
```

---

### `routes/student_routes.py` - Student Dashboard & Viva

```python
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from functools import wraps

from extensions import db
from models.user import VivaSession, VivaSchedule, StudentAnswer, Experiment
from services.perplexity_service import generate_mcq_questions as perplexity_generate_mcqs

student_bp = Blueprint('student', __name__)

IST_OFFSET = timedelta(hours=5, minutes=30)

def get_ist_now():
    return datetime.utcnow() + IST_OFFSET

def get_ist_today():
    return get_ist_now().date()


def student_required(f):
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
    from models.user import Subject
    
    lab_subjects = Subject.query.filter_by(is_lab=True).all()
    my_sessions = VivaSession.query.filter_by(student_id=current_user.id).all()
    session_by_exp = {s.experiment_id: s for s in my_sessions}
    
    labs_data = []
    for subject in lab_subjects:
        for lab in subject.labs:
            lab_info = {'lab': lab, 'subject': subject, 'experiments': []}
            for exp in lab.experiments:
                schedule = VivaSchedule.query.filter_by(experiment_id=exp.id).first()
                session = session_by_exp.get(exp.id)
                
                exp_info = {
                    'experiment': exp, 'schedule': schedule,
                    'session': session, 'status': 'not_scheduled'
                }
                
                if schedule:
                    today_ist = get_ist_today()
                    if session:
                        exp_info['status'] = session.status
                    elif schedule.is_active_now():
                        exp_info['status'] = 'available'
                    elif schedule.scheduled_date > today_ist:
                        exp_info['status'] = 'upcoming'
                    elif schedule.scheduled_date < today_ist:
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
    
    if not schedule.is_active_now():
        flash('Viva is not available at this time.', 'warning')
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
    
    # Create new session with AI-generated questions
    try:
        viva_session = VivaSession(
            student_id=current_user.id,
            schedule_id=schedule.id,
            experiment_id=experiment_id,
            status='in_progress',
            total_marks=10,
            started_at=datetime.utcnow()
        )
        
        # Generate MCQ questions using Perplexity AI
        questions = perplexity_generate_mcqs(
            experiment_title=experiment.title,
            experiment_description=experiment.description or '',
            lab_name=experiment.lab_config.lab_name,
            student_id=current_user.id,
            num_questions=10
        )
        viva_session.generated_questions = questions
        
        schedule.enrolled_count += 1
        db.session.add(viva_session)
        db.session.commit()
        
        return redirect(url_for('student.attempt_viva', viva_session_id=viva_session.id))
    except Exception as e:
        db.session.rollback()
        flash(f'Error starting viva: {str(e)}', 'danger')
        return redirect(url_for('student.dashboard'))


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
        return redirect(url_for('student.view_marks', viva_id=viva_session_id))
    
    if not viva.schedule.is_active_now():
        viva.finalize_violation('Time window expired')
        db.session.commit()
        flash('The viva time window has expired.', 'warning')
        return redirect(url_for('student.view_marks', viva_id=viva_session_id))
    
    experiment = viva.experiment
    questions = viva.generated_questions or []
    
    answered = StudentAnswer.query.filter_by(viva_session_id=viva_session_id).all()
    answers_dict = {a.question_number: a.answer_text for a in answered}
    
    return render_template('student/viva_interface.html',
                         viva=viva, experiment=experiment,
                         questions=questions, answers_dict=answers_dict)


@student_bp.route('/viva/marks/<int:viva_id>')
@login_required
@student_required
def view_marks(viva_id):
    """View viva marks and feedback"""
    viva = VivaSession.query.get_or_404(viva_id)
    
    if viva.student_id != current_user.id:
        flash('You do not have permission.', 'danger')
        return redirect(url_for('student.dashboard'))
    
    answers = StudentAnswer.query.filter_by(viva_session_id=viva_id).order_by(StudentAnswer.question_number).all()
    
    return render_template('student/view_marks.html', viva=viva, answers=answers)
```

---

### `routes/api_routes.py` - REST API

```python
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime

from extensions import db
from models.user import StudentAnswer, VivaSession
from services.perplexity_service import evaluate_mcq_answers
from services.sheets_service import get_sheets_service

api_bp = Blueprint('api', __name__)


@api_bp.route('/viva/<int:viva_session_id>/submit-answer', methods=['POST'])
@login_required
def submit_answer(viva_session_id):
    """Submit answer to a question"""
    try:
        data = request.get_json()
        viva = VivaSession.query.get_or_404(viva_session_id)
        
        if viva.student_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        question_number = data.get('question_number')
        answer_text = data.get('answer_text')
        
        existing = StudentAnswer.query.filter_by(
            viva_session_id=viva_session_id,
            question_number=question_number
        ).first()
        
        if existing:
            existing.answer_text = answer_text
            existing.updated_at = datetime.utcnow()
        else:
            new_answer = StudentAnswer(
                viva_session_id=viva_session_id,
                question_number=question_number,
                answer_text=answer_text
            )
            db.session.add(new_answer)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Answer saved',
            'question_number': question_number
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/viva/<int:viva_session_id>/submit', methods=['POST'])
@login_required
def submit_viva(viva_session_id):
    """Submit completed viva - evaluates MCQ answers"""
    try:
        viva = VivaSession.query.get_or_404(viva_session_id)
        
        if viva.student_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        if viva.status in ['completed', 'violated']:
            return jsonify({'error': 'Viva already submitted'}), 400
        
        answers = StudentAnswer.query.filter_by(viva_session_id=viva_session_id).all()
        student_answers = {a.question_number: a.answer_text for a in answers}
        
        questions = viva.generated_questions or []
        
        if questions:
            result = evaluate_mcq_answers(questions, student_answers)
            viva.obtained_marks = result['obtained_marks']
            
            for r in result['results']:
                ans = next((a for a in answers if a.question_number == r['question_number']), None)
                if ans:
                    ans.marks_obtained = r['marks']
        else:
            viva.obtained_marks = len(answers)
        
        viva.status = 'completed'
        viva.completed_at = datetime.utcnow()
        
        db.session.commit()
        
        # Write marks to Google Sheets
        sheets = get_sheets_service()
        if sheets and viva.experiment and current_user.roll_number:
            sheets.update_student_experiment_mark(
                reg_no=current_user.roll_number,
                experiment_no=viva.experiment.experiment_no,
                marks=viva.obtained_marks
            )
        
        return jsonify({
            'success': True,
            'message': 'Viva submitted successfully',
            'obtained_marks': viva.obtained_marks,
            'total_marks': viva.total_marks
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/viva/<int:viva_session_id>/violation', methods=['POST'])
@login_required
def report_violation(viva_session_id):
    """Report anti-cheat violation - finalizes viva with 0 marks"""
    try:
        viva = VivaSession.query.get_or_404(viva_session_id)
        
        if viva.student_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        if viva.status in ['completed', 'violated']:
            return jsonify({'error': 'Viva already finalized'}), 400
        
        data = request.get_json() or {}
        reason = data.get('reason', 'Violation detected')
        
        viva.violation_count = (viva.violation_count or 0) + 1
        viva.finalize_violation(reason)
        db.session.commit()
        
        # Write 0 marks to Google Sheets
        sheets = get_sheets_service()
        if sheets and viva.experiment and current_user.roll_number:
            sheets.update_student_experiment_mark(
                reg_no=current_user.roll_number,
                experiment_no=viva.experiment.experiment_no,
                marks=0
            )
        
        return jsonify({
            'success': True,
            'message': 'Violation recorded. Viva finalized with 0 marks.',
            'violation_reason': reason
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
```

---

### `services/perplexity_service.py` - AI MCQ Generation

```python
"""Perplexity AI Service for MCQ generation and chatbot"""
import requests
import json
import logging
import os

logger = logging.getLogger(__name__)

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"


def get_chat_response(messages, context=None):
    """Get a response from Perplexity AI"""
    try:
        system_message = """You are an AI assistant for the Lab Viva Assistant platform. 
You help students prepare for lab viva examinations."""

        if context:
            system_message += f"\n\nCurrent context: {context}"

        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }

        api_messages = [{"role": "system", "content": system_message}]
        api_messages.extend(messages)

        payload = {
            "model": "sonar",
            "messages": api_messages,
            "max_tokens": 1024,
            "temperature": 0.7
        }

        response = requests.post(PERPLEXITY_API_URL, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            return {'success': True, 'response': data['choices'][0]['message']['content']}
        else:
            return {'success': False, 'error': f"API Error: {response.status_code}"}

    except Exception as e:
        return {'success': False, 'error': str(e)}


def generate_mcq_questions(experiment_title, experiment_description, lab_name, student_id, num_questions=10):
    """Generate MCQ questions using Perplexity API"""
    import random
    import time
    
    unique_seed = int(time.time() * 1000) + (student_id * 17) + random.randint(1, 10000)
    
    if not PERPLEXITY_API_KEY:
        return _generate_fallback_mcqs(experiment_title, num_questions)
    
    prompt = f"""Generate exactly {num_questions} UNIQUE MCQs for a lab viva.

Lab: {lab_name}
Experiment: {experiment_title}
Description: {experiment_description}

Requirements:
1. {num_questions} MCQ questions
2. Each with 4 options (A, B, C, D)
3. Only ONE correct answer
4. RANDOMIZATION SEED: {unique_seed}

Return ONLY valid JSON array:
[{{"question_number": 1, "question": "...", "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, "correct_answer": "A"}}]"""

    try:
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": "Generate MCQ questions in valid JSON format only."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 4096,
            "temperature": 1.0
        }

        response = requests.post(PERPLEXITY_API_URL, headers=headers, json=payload, timeout=60)

        if response.status_code == 200:
            data = response.json()
            response_text = data['choices'][0]['message']['content'].strip()
            
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1])
            
            questions = json.loads(response_text)
            
            if isinstance(questions, list) and len(questions) >= num_questions:
                for i, q in enumerate(questions):
                    q['question_number'] = i + 1
                return questions[:num_questions]
        
        return _generate_fallback_mcqs(experiment_title, num_questions)
        
    except Exception as e:
        logger.error(f"MCQ generation error: {e}")
        return _generate_fallback_mcqs(experiment_title, num_questions)


def _generate_fallback_mcqs(experiment_title, num_questions):
    """Generate fallback MCQs if API fails"""
    import random
    
    templates = [
        {'q': 'What is an algorithm?', 'a': 'A', 'opts': {'A': 'Step-by-step procedure', 'B': 'Programming language', 'C': 'Data structure', 'D': 'Hardware'}},
        {'q': 'What does Big-O notation represent?', 'a': 'C', 'opts': {'A': 'Best case', 'B': 'Average case', 'C': 'Upper bound', 'D': 'Lower bound'}},
        {'q': 'Which uses LIFO principle?', 'a': 'B', 'opts': {'A': 'Queue', 'B': 'Stack', 'C': 'Array', 'D': 'Linked List'}},
        {'q': 'Binary search requires?', 'a': 'A', 'opts': {'A': 'Sorted array', 'B': 'Unsorted array', 'C': 'Linked list', 'D': 'None'}},
        {'q': 'Time complexity of linear search?', 'a': 'B', 'opts': {'A': 'O(1)', 'B': 'O(n)', 'C': 'O(log n)', 'D': 'O(n²)'}},
    ]
    
    random.shuffle(templates)
    questions = []
    
    for i in range(num_questions):
        if i < len(templates):
            t = templates[i]
            questions.append({
                'question_number': i + 1,
                'question': t['q'],
                'options': t['opts'],
                'correct_answer': t['a']
            })
        else:
            questions.append({
                'question_number': i + 1,
                'question': f'Question {i+1} about {experiment_title}?',
                'options': {'A': 'Option A', 'B': 'Option B', 'C': 'Option C', 'D': 'All of the above'},
                'correct_answer': 'D'
            })
    
    return questions


def evaluate_mcq_answers(questions, student_answers):
    """Evaluate student MCQ answers"""
    results = []
    obtained_marks = 0
    
    for q in questions:
        q_num = q['question_number']
        correct = q['correct_answer']
        student_ans = student_answers.get(q_num, '')
        is_correct = student_ans.upper() == correct.upper() if student_ans else False
        marks = 1 if is_correct else 0
        obtained_marks += marks
        
        results.append({
            'question_number': q_num,
            'correct_answer': correct,
            'student_answer': student_ans,
            'is_correct': is_correct,
            'marks': marks
        })
    
    return {
        'total_marks': len(questions),
        'obtained_marks': obtained_marks,
        'results': results
    }
```

---

## 🎨 JavaScript Source Code

### `static/js/anticheat.js` - Anti-Cheat Module

```javascript
/**
 * Enhanced Anti-cheat module for viva interface
 * 
 * Security Features:
 * - Force fullscreen mode on entry
 * - Auto-submit viva if fullscreen exits
 * - Detect tab switches and window blur
 * - Block right-click, copy, paste, cut
 * - Block keyboard shortcuts (F12, Escape, Tab, Ctrl, Alt)
 * - Immediately reports violations to server (0 marks)
 */

(function() {
    'use strict';
    
    let vivaSessionId = null;
    let isVivaActive = false;
    let violationReported = false;
    let fullscreenEntered = false;
    
    function init(sessionId) {
        vivaSessionId = sessionId;
        isVivaActive = true;
        violationReported = false;
        fullscreenEntered = false;
        
        bindFullscreenChange();
        bindVisibilityChange();
        bindWindowBlur();
        bindCopyPaste();
        bindContextMenu();
        bindKeyboardShortcuts();
        bindBeforeUnload();
        
        setTimeout(() => requestFullscreen(), 500);
    }
    
    function requestFullscreen() {
        const elem = document.documentElement;
        if (elem.requestFullscreen) {
            elem.requestFullscreen().then(() => {
                fullscreenEntered = true;
            }).catch(err => {
                showFullscreenWarning();
            });
        }
    }
    
    function handleFullscreenChange() {
        const isFullscreen = !!(document.fullscreenElement || document.webkitFullscreenElement);
        if (!isFullscreen && isVivaActive && fullscreenEntered) {
            reportViolation('Fullscreen mode exited - Viva terminated');
        }
    }
    
    function reportViolation(reason) {
        if (violationReported || !isVivaActive || !vivaSessionId) return;
        
        violationReported = true;
        isVivaActive = false;
        
        fetch(`/api/viva/${vivaSessionId}/violation`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrf_token')
            },
            body: JSON.stringify({ reason: reason })
        })
        .then(() => {
            showViolationAlert(reason);
            setTimeout(() => {
                window.location.href = `/student/viva/marks/${vivaSessionId}`;
            }, 3000);
        })
        .catch(() => {
            showViolationAlert(reason);
            setTimeout(() => {
                window.location.href = `/student/viva/marks/${vivaSessionId}`;
            }, 3000);
        });
    }
    
    function bindVisibilityChange() {
        document.addEventListener('visibilitychange', function() {
            if (document.hidden && isVivaActive) {
                reportViolation('Tab switch detected');
            }
        });
    }
    
    function bindCopyPaste() {
        document.addEventListener('copy', e => {
            if (isVivaActive) {
                e.preventDefault();
                reportViolation('Copy attempt detected');
            }
        });
        document.addEventListener('paste', e => {
            if (isVivaActive) {
                e.preventDefault();
                reportViolation('Paste attempt detected');
            }
        });
    }
    
    function bindContextMenu() {
        document.addEventListener('contextmenu', e => {
            if (isVivaActive) {
                e.preventDefault();
                showWarningToast('Right-click is disabled during viva');
            }
        });
    }
    
    function bindKeyboardShortcuts() {
        document.addEventListener('keydown', function(e) {
            if (!isVivaActive) return;
            
            if (e.key === 'Escape' || e.key === 'F12') {
                e.preventDefault();
                if (e.key === 'F12') reportViolation('Developer tools access attempt');
            }
            
            if (e.ctrlKey) {
                e.preventDefault();
                if (['c', 'v', 'x'].includes(e.key)) {
                    reportViolation(`Clipboard shortcut (Ctrl+${e.key.toUpperCase()})`);
                }
            }
            
            if (e.altKey && e.key === 'Tab') {
                e.preventDefault();
                reportViolation('Alt+Tab detected');
            }
        });
    }
    
    function disable() {
        isVivaActive = false;
        violationReported = true;
        if (document.fullscreenElement) {
            document.exitFullscreen().catch(() => {});
        }
    }
    
    window.AntiCheat = {
        init: init,
        disable: disable,
        reportViolation: reportViolation,
        requestFullscreen: requestFullscreen
    };
})();
```

---

### `static/js/chatbot.js` - AI Chatbot Widget

```javascript
/**
 * Floating Chatbot Widget
 */
class ChatbotWidget {
    constructor() {
        this.isOpen = false;
        this.conversationHistory = [];
        this.csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
        this.init();
    }

    init() {
        this.createWidget();
        this.bindEvents();
    }

    createWidget() {
        // Create floating button
        const floatingBtn = document.createElement('div');
        floatingBtn.id = 'chatbot-floating-btn';
        floatingBtn.innerHTML = '<i class="fas fa-robot"></i>';
        floatingBtn.title = 'AI Study Assistant';
        document.body.appendChild(floatingBtn);

        // Create chat window
        const chatWindow = document.createElement('div');
        chatWindow.id = 'chatbot-window';
        chatWindow.innerHTML = `
            <div class="chatbot-header">
                <div class="chatbot-title">
                    <i class="fas fa-robot"></i>
                    <span>AI Assistant</span>
                </div>
                <button class="chatbot-close" id="chatbot-close">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="chatbot-messages" id="chatbot-messages">
                <div class="message bot-message">
                    <div class="message-content">
                        Hi! 👋 I'm your AI Study Assistant. Ask me anything!
                    </div>
                </div>
            </div>
            <div class="chatbot-input-area">
                <input type="text" id="chatbot-input" placeholder="Ask a question...">
                <button id="chatbot-send"><i class="fas fa-paper-plane"></i></button>
            </div>
        `;
        document.body.appendChild(chatWindow);
        this.addStyles();
    }

    async sendMessage() {
        const input = document.getElementById('chatbot-input');
        const message = input.value.trim();
        if (!message) return;

        this.addMessage(message, true);
        this.conversationHistory.push({ role: 'user', content: message });

        input.value = '';
        this.showTyping();

        try {
            const response = await fetch('/chatbot/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({ messages: this.conversationHistory })
            });

            const data = await response.json();
            this.hideTyping();

            if (data.success) {
                this.addMessage(data.response);
                this.conversationHistory.push({ role: 'assistant', content: data.response });
            } else {
                this.addMessage('Sorry, I encountered an error.');
            }
        } catch {
            this.hideTyping();
            this.addMessage('Network error. Please try again.');
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.chatbotWidget = new ChatbotWidget();
});
```

---

## 🎨 CSS (Key Styles)

The main stylesheet (`static/css/style.css`) contains ~900 lines of CSS including:

- **CSS Variables** for theming (primary, secondary, success, danger colors)
- **Navigation** with gradient background and dropdown menus
- **Forms** with focus states and validation styling
- **Cards** for dashboard stats and viva items
- **Buttons** (primary, secondary, success, danger variants)
- **Alerts** with animations
- **Responsive Design** with media queries

---

## 📄 Environment Variables (.env)

```env
# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your-secret-key

# Database
SQLALCHEMY_DATABASE_URI=sqlite:///app.db

# Perplexity API
PERPLEXITY_API_KEY=pplx-xxxxxxxxxxxx

# Google Sheets
GOOGLE_SHEETS_CREDENTIALS_PATH=credentials.json
GOOGLE_SHEET_ID=xxxxxxxxxxxxxxx
GOOGLE_TEACHER_SHEET_ID=xxxxxxxxxxxxxxx
```

---

## 🚀 Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python app.py
```

Access at: `http://localhost:5000`

---

## 📊 Key Features

1. **AI-Generated MCQs**: Unique questions per student via Perplexity API
2. **Anti-Cheat System**: Fullscreen enforcement, tab detection, keyboard blocking
3. **Google Sheets Integration**: Marks sync, student validation
4. **Role-Based Access**: Separate dashboards for students/teachers
5. **Real-time Grading**: Automatic MCQ evaluation
6. **Time-Window Enforcement**: Viva only during scheduled slots
