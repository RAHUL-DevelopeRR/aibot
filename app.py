from dotenv import load_dotenv
load_dotenv()  # Load .env file before anything else

from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_login import current_user
from flask_wtf.csrf import generate_csrf
from config import config
from extensions import db, login_manager, csrf
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
    
    # User loader - must be outside app_context
    @login_manager.user_loader
    def load_user(user_id):
        from models.user import User
        return User.query.get(int(user_id))
    
    # Register blueprints - outside app_context
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
    
    # Create tables - needs app_context
    with app.app_context():
        db.create_all()
    
    # Register error handlers - return JSON for API routes
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
        """Convert UTC datetime to IST"""
        if dt is None:
            return None
        return dt + IST_OFFSET

    return app


# Create app instance for WSGI servers (Vercel, Render, Gunicorn)
app = create_app(os.environ.get('FLASK_ENV', 'development'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
