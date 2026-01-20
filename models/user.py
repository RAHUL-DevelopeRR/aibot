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
    designation = db.Column(db.String(100))  # e.g., 'Assistant Professor'
    department = db.Column(db.String(100))
    years_handling = db.Column(db.JSON, default=[])  # e.g., ['II', 'III', 'IV']
    
    # Relationships
    viva_sessions = db.relationship('VivaSession', backref='student', lazy=True, foreign_keys='VivaSession.student_id')
    schedules = db.relationship('VivaSchedule', backref='teacher', lazy=True, foreign_keys='VivaSchedule.teacher_id')
    teacher_subjects = db.relationship('TeacherSubject', backref='teacher', lazy=True, foreign_keys='TeacherSubject.teacher_id')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.email}>'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class TeacherSubject(db.Model):
    """Teacher-Subject mapping"""
    __tablename__ = 'teacher_subjects'
    
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    year = db.Column(db.String(10))  # 'II', 'III', 'IV'
    
    __table_args__ = (
        db.UniqueConstraint('teacher_id', 'subject_id', 'year', name='unique_teacher_subject_year'),
    )


class Subject(db.Model):
    """Subject model"""
    __tablename__ = 'subjects'
    
    id = db.Column(db.Integer, primary_key=True)
    subject_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    subject_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    is_lab = db.Column(db.Boolean, default=False)  # True if lab subject, False if theory
    year = db.Column(db.String(10))  # 'II', 'III', 'IV'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    labs = db.relationship('LabConfig', backref='subject', lazy=True, cascade='all, delete-orphan')
    teacher_subjects = db.relationship('TeacherSubject', backref='subject', lazy=True)
    
    def __repr__(self):
        return f'<Subject {self.subject_code}>'


class LabConfig(db.Model):
    """Lab configuration model"""
    __tablename__ = 'lab_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    lab_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    total_experiments = db.Column(db.Integer, default=10)  # Number of experiments in lab
    materials_text = db.Column(db.Text)  # Lab materials for Gemini context
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    experiments = db.relationship('Experiment', backref='lab_config', lazy=True, cascade='all, delete-orphan', order_by='Experiment.experiment_no')
    
    def __repr__(self):
        return f'<LabConfig {self.lab_name}>'


class Experiment(db.Model):
    """Experiment model - 10 experiments per lab"""
    __tablename__ = 'experiments'
    
    id = db.Column(db.Integer, primary_key=True)
    lab_config_id = db.Column(db.Integer, db.ForeignKey('lab_configs.id'), nullable=False)
    experiment_no = db.Column(db.Integer, nullable=False)  # 1-10
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    materials_text = db.Column(db.Text)  # Experiment-specific materials for Gemini
    total_marks = db.Column(db.Integer, default=10)  # 10 MCQs x 1 mark each
    duration_minutes = db.Column(db.Integer, default=15)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    schedules = db.relationship('VivaSchedule', backref='experiment', lazy=True, cascade='all, delete-orphan')
    viva_sessions = db.relationship('VivaSession', backref='experiment', lazy=True, cascade='all, delete-orphan')
    
    __table_args__ = (
        db.UniqueConstraint('lab_config_id', 'experiment_no', name='unique_experiment'),
    )
    
    def __repr__(self):
        return f'<Experiment {self.experiment_no}: {self.title}>'


class VivaSchedule(db.Model):
    """Viva schedule model - per experiment"""
    __tablename__ = 'viva_schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    experiment_id = db.Column(db.Integer, db.ForeignKey('experiments.id'), nullable=False)
    scheduled_date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.String(5), nullable=False)  # HH:MM format
    end_time = db.Column(db.String(5), nullable=False)
    total_slots = db.Column(db.Integer, default=50)
    enrolled_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='scheduled')  # scheduled, active, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    viva_sessions = db.relationship('VivaSession', backref='schedule', lazy=True, cascade='all, delete-orphan')
    
    def is_active_now(self):
        """Check if schedule is currently active (within time window)"""
        from datetime import date, time
        now = datetime.utcnow()
        today = now.date()
        current_time = now.time()
        
        if self.scheduled_date != today:
            return False
        
        start = datetime.strptime(self.start_time, '%H:%M').time()
        end = datetime.strptime(self.end_time, '%H:%M').time()
        
        return start <= current_time <= end
    
    def __repr__(self):
        return f'<VivaSchedule Exp {self.experiment_id} on {self.scheduled_date}>'


class VivaSession(db.Model):
    """Viva session model - per student per experiment"""
    __tablename__ = 'viva_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    schedule_id = db.Column(db.Integer, db.ForeignKey('viva_schedules.id'), nullable=False)
    experiment_id = db.Column(db.Integer, db.ForeignKey('experiments.id'), nullable=False)
    status = db.Column(db.String(20), default='scheduled')  # scheduled, in_progress, completed, violated
    total_marks = db.Column(db.Integer, default=10)  # 10 MCQs x 1 mark
    obtained_marks = db.Column(db.Integer, default=0)
    
    # MCQ questions generated for this student (JSON array of {question, options, correct_answer})
    generated_questions = db.Column(db.JSON, default=[])
    
    # Anti-cheat violation tracking
    violation_detected = db.Column(db.Boolean, default=False)
    violation_reason = db.Column(db.String(255))
    violation_count = db.Column(db.Integer, default=0)
    
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    answers = db.relationship('StudentAnswer', backref='viva_session', lazy=True, cascade='all, delete-orphan')
    
    def finalize_violation(self, reason):
        """Finalize session with 0 marks due to violation"""
        self.violation_detected = True
        self.violation_reason = reason
        self.obtained_marks = 0
        self.status = 'violated'
        self.completed_at = datetime.utcnow()
    
    def __repr__(self):
        return f'<VivaSession {self.id}>'


class StudentAnswer(db.Model):
    """Student answer model"""
    __tablename__ = 'student_answers'
    
    id = db.Column(db.Integer, primary_key=True)
    viva_session_id = db.Column(db.Integer, db.ForeignKey('viva_sessions.id'), nullable=False)
    question_number = db.Column(db.Integer, nullable=False)
    answer_text = db.Column(db.Text)
    marks_obtained = db.Column(db.Integer)
    teacher_feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('viva_session_id', 'question_number', name='unique_answer'),
    )
    
    def __repr__(self):
        return f'<StudentAnswer Q{self.question_number}>'


class AuditLog(db.Model):
    """Audit log model for tracking actions"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f'<AuditLog {self.action}>'
