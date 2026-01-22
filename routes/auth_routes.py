from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from extensions import db
from models.user import User
from werkzeug.security import generate_password_hash
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
            if not next_page or url_has_allowed_host_and_scheme(next_page):
                next_page = url_for('student.dashboard') if user.role == 'student' else url_for('teacher.dashboard')
            return redirect(next_page)
        else:
            flash('Invalid email, password, or role.', 'danger')
    
    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if current_user.is_authenticated:
        if current_user.role == 'student':
            return redirect(url_for('student.dashboard'))
        else:
            return redirect(url_for('teacher.dashboard'))
    
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
                    flash('Registration Number not found in student records. Please contact your teacher.', 'danger')
                    return redirect(url_for('auth.register'))
                # Use name from Google Sheets if available
                if student_data.get('name'):
                    name = student_data['name']
            else:
                flash('Unable to verify registration number. Please try again later.', 'warning')
                return redirect(url_for('auth.register'))
        
        # Create user
        user = User(
            name=name,
            email=email,
            roll_number=roll_number.strip().upper(),  # Normalize Reg_No
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


def url_has_allowed_host_and_scheme(url, allowed_hosts=None):
    """Security check for redirect URLs"""
    from urllib.parse import urlparse
    if allowed_hosts is None:
        allowed_hosts = {'localhost', '127.0.0.1'}
    parsed_url = urlparse(url)
    return not parsed_url.netloc or parsed_url.netloc in allowed_hosts
