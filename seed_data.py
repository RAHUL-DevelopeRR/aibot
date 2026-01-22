"""Seed data script for Lab Viva Assistant

NOTE: Experiments are now loaded from Google Sheets via the sync service.
This file only creates test users. Use the teacher dashboard to sync experiments.
"""
from app import create_app, db
from models.user import User, Subject, LabConfig, Experiment
from services.sync_service import sync_experiments_from_sheets

def seed_database():
    app = create_app()
    with app.app_context():
        # Create test users
        # Teacher
        teacher = User.query.filter_by(email='teacher@test.com').first()
        if not teacher:
            teacher = User(
                name='Dr. Smith',
                email='teacher@test.com',
                roll_number='T001',
                role='teacher',
                designation='Assistant Professor / Head of Department',
                department='Computer Science and Business Systems',
                years_handling=['II', 'III', 'IV']
            )
            teacher.set_password('password123')
            db.session.add(teacher)
        
        # Student
        student = User.query.filter_by(email='student@test.com').first()
        if not student:
            student = User(
                name='John Doe',
                email='student@test.com',
                roll_number='CS2021001',
                role='student'
            )
            student.set_password('password123')
            db.session.add(student)
        
        db.session.commit()
        print('Seed data created successfully!')
        print('Test credentials:')
        print('  Teacher: teacher@test.com / password123')
        print('  Student: student@test.com / password123')
        
        # Auto-sync experiments from Google Sheets
        print('\nAttempting to sync experiments from Google Sheets...')
        result = sync_experiments_from_sheets()
        if result['success']:
            print(f"✓ {result['message']}")
        else:
            print(f"⚠ {result['message']}")
            print('  You can manually sync from the teacher dashboard.')

if __name__ == '__main__':
    seed_database()
