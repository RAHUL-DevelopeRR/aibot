from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from extensions import db
from models.user import User
from werkzeug.security import generate_password_hash
from services.sheets_service import get_sheets_service

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login - uses Reg_No + Name verification against Google Sheets"""
    if current_user.is_authenticated:
        if current_user.role == 'student':
            return redirect(url_for('student.dashboard'))
        else:
            return redirect(url_for('teacher.dashboard'))
    
    if request.method == 'POST':
        roll_number = request.form.get('roll_number', '').strip()
        name = request.form.get('name', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', '').strip()
        
        # For students: Login via Java Backend (DB only, no Google Sheets check)
        if role == 'student':
            # Password is MANDATORY
            if not all([roll_number, password]):
                flash('Registration Number and Password are required.', 'danger')
                return redirect(url_for('auth.login'))
            
            # Authenticate via Java Backend (uses database, NOT Google Sheets)
            try:
                from services.backend_service import get_backend_service
                backend = get_backend_service()
                
                if backend.is_enabled:
                    result = backend.login_student(roll_number, password)
                    
                    if result.get('success'):
                        # Create or update local user for flask-login compatibility
                        normalized_reg = _normalize_reg_no(roll_number)
                        user = User.query.filter_by(roll_number=normalized_reg).first()
                        
                        if not user:
                            # Create local user record synced from backend
                            user = User(
                                name=result.get('name', ''),
                                email=result.get('email', f"{normalized_reg}@student.local"),
                                roll_number=normalized_reg,
                                role='student'
                            )
                            user.set_password(password)
                            db.session.add(user)
                            db.session.commit()
                        
                        # Store JWT token in session for backend API calls
                        from flask import session
                        session['backend_token'] = result.get('token')
                        session['backend_user_id'] = result.get('user_id')
                        
                        login_user(user, remember=True)
                        return redirect(url_for('student.dashboard'))
                    else:
                        flash(result.get('error', 'Invalid credentials'), 'danger')
                        return redirect(url_for('auth.login'))
            except Exception as e:
                print(f"[AuthRoutes] Backend auth failed, falling back to local: {e}")
            
            # Fallback to local SQLite authentication (offline mode)
            user = User.query.filter_by(roll_number=_normalize_reg_no(roll_number)).first()
            
            if not user:
                flash('Account not found. Please register first.', 'danger')
                return redirect(url_for('auth.register'))
            
            if not user.check_password(password):
                flash('Invalid password.', 'danger')
                return redirect(url_for('auth.login'))
            
            login_user(user, remember=True)
            return redirect(url_for('student.dashboard'))
        
        # For teachers: Use traditional email/password login
        else:
            email = request.form.get('email', '').strip()
            faculty_password = request.form.get('faculty_password', '').strip()
            
            if not all([email, faculty_password]):
                flash('Email and password are required for faculty.', 'danger')
                return redirect(url_for('auth.login'))
            
            user = User.query.filter_by(email=email, role='teacher').first()
            
            if user and user.check_password(faculty_password):
                login_user(user, remember=True)
                return redirect(url_for('teacher.dashboard'))
            else:
                flash('Invalid email or password.', 'danger')
    
    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration - Reg_No + Name required, Email optional"""
    if current_user.is_authenticated:
        if current_user.role == 'student':
            return redirect(url_for('student.dashboard'))
        else:
            return redirect(url_for('teacher.dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()  # Optional for students
        roll_number = request.form.get('roll_number', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        role = request.form.get('role', '').strip()
        
        # Validation
        if role == 'student':
            # Reg_No and Name are REQUIRED for students
            if not all([name, roll_number]):
                flash('Registration Number and Name are required.', 'danger')
                return redirect(url_for('auth.register'))
            
            # Verify BOTH Reg_No AND Name against Google Sheets
            sheets = get_sheets_service()
            if sheets:
                student_data = sheets.validate_student_by_reg_and_name(roll_number, name)
                if not student_data:
                    flash('Registration number and name not found in student records. Please ensure both match exactly.', 'danger')
                    return redirect(url_for('auth.register'))
                
                # Use name from Google Sheets (authoritative)
                name = student_data['name']
            else:
                flash('Unable to verify student records. Please try again later.', 'warning')
                return redirect(url_for('auth.register'))
            
            # Normalize Reg_No
            normalized_reg_no = _normalize_reg_no(roll_number)
            
            # Check if already registered locally
            if User.query.filter_by(roll_number=normalized_reg_no).first():
                flash('This registration number is already registered. Please login instead.', 'danger')
                return redirect(url_for('auth.login'))
            
            # Password defaults to Reg_No if not provided
            if not password:
                password = roll_number
            
            # Email is optional for students
            if not email:
                email = f"{normalized_reg_no.lower()}@mkce.ac.in"
            
            # Try registering via Java Backend first
            try:
                from services.backend_service import get_backend_service
                backend = get_backend_service()
                
                if backend.is_enabled:
                    result = backend.register_student(roll_number, name, password, email)
                    
                    if result.get('success'):
                        # Create local user record synced from backend
                        user = User(
                            name=result.get('name', name),
                            email=result.get('email', email),
                            roll_number=normalized_reg_no,
                            role='student'
                        )
                        user.set_password(password)
                        db.session.add(user)
                        db.session.commit()
                        
                        flash('Registration successful! Please log in.', 'success')
                        return redirect(url_for('auth.login'))
                    else:
                        # Backend registration failed - show error but allow local registration
                        print(f"[AuthRoutes] Backend registration failed: {result.get('error')}")
            except Exception as e:
                print(f"[AuthRoutes] Backend registration error, using local: {e}")
            
            # Fallback to local-only registration
            user = User(
                name=name,
                email=email,
                roll_number=normalized_reg_no,
                role='student'
            )
            user.set_password(password)
            
        else:
            # Teachers: Traditional registration with email/password
            # Read teacher-specific form fields
            teacher_name = request.form.get('teacher_name', '').strip()
            teacher_email = request.form.get('teacher_email', '').strip()
            teacher_password = request.form.get('teacher_password', '').strip()
            teacher_confirm = request.form.get('teacher_confirm', '').strip()
            
            if not all([teacher_name, teacher_email, teacher_password]):
                flash('Name, Email, and Password are required for faculty.', 'danger')
                return redirect(url_for('auth.register'))
            
            if len(teacher_password) < 6:
                flash('Password must be at least 6 characters.', 'danger')
                return redirect(url_for('auth.register'))
            
            if teacher_password != teacher_confirm:
                flash('Passwords do not match.', 'danger')
                return redirect(url_for('auth.register'))
            
            if User.query.filter_by(email=teacher_email).first():
                flash('Email already registered.', 'danger')
                return redirect(url_for('auth.register'))
            
            user = User(
                name=teacher_name,
                email=teacher_email,
                roll_number='',
                role='teacher'
            )
            user.set_password(teacher_password)
        
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


def url_has_allowed_host_and_scheme(url, allowed_hosts=None):
    """Security check for redirect URLs"""
    from urllib.parse import urlparse
    if allowed_hosts is None:
        allowed_hosts = {'localhost', '127.0.0.1'}
    parsed_url = urlparse(url)
    return not parsed_url.netloc or parsed_url.netloc in allowed_hosts


def _normalize_reg_no(reg_no: str) -> str:
    """Normalize registration number - uppercase, remove spaces/special chars"""
    import re
    if not reg_no:
        return ''
    return re.sub(r'[^A-Z0-9]', '', reg_no.upper())
