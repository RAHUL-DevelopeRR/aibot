from flask import Flask, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, generate_csrf
from config import config
import os

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


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
    
    with app.app_context():
        # Register blueprints
        from routes.auth_routes import auth_bp
        from routes.student_routes import student_bp
        from routes.teacher_routes import teacher_bp
        from routes.api_routes import api_bp
        
        app.register_blueprint(auth_bp)
        app.register_blueprint(student_bp, url_prefix='/student')
        app.register_blueprint(teacher_bp, url_prefix='/teacher')
        app.register_blueprint(api_bp, url_prefix='/api')
        
        # Create tables
        db.create_all()
        
        # Register error handlers
        @app.errorhandler(404)
        def not_found(error):
            return render_template('errors/404.html'), 404
        
        @app.errorhandler(403)
        def forbidden(error):
            return render_template('errors/403.html'), 403
        
        @app.errorhandler(500)
        def internal_error(error):
            db.session.rollback()
            return render_template('errors/500.html'), 500
        
        # Home route
        @app.route('/')
        def index():
            from flask_login import current_user

            if current_user.is_authenticated:
                if current_user.role == 'student':
                    return redirect(url_for('student.dashboard'))
                if current_user.role == 'teacher':
                    return redirect(url_for('teacher.dashboard'))

            return redirect(url_for('auth.login'))

    # Make csrf_token available in templates and generate cookie
    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token=generate_csrf)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
