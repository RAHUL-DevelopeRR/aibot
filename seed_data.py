"""Seed data script for Lab Viva Assistant"""
from app import create_app, db
from models.user import User, Subject, LabConfig, Experiment

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
                designation='Assistant Professor',
                department='Computer Science',
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
        
        # Create a lab subject
        subject = Subject.query.filter_by(subject_code='CS301L').first()
        if not subject:
            subject = Subject(
                subject_code='CS301L',
                subject_name='Data Structures Lab',
                description='Practical implementation of data structures',
                is_lab=True,
                year='III'
            )
            db.session.add(subject)
            db.session.flush()
            
            # Create lab config
            lab = LabConfig(
                subject_id=subject.id,
                lab_name='Data Structures Laboratory',
                description='Implementation of various data structures',
                total_experiments=10,
                materials_text='Topics include arrays, linked lists, stacks, queues, trees, graphs, sorting, searching algorithms.'
            )
            db.session.add(lab)
            db.session.flush()
            
            # Create 10 experiments
            experiments = [
                'Array Operations and Applications',
                'Linked List Implementation',
                'Stack Operations and Applications',
                'Queue Implementation',
                'Binary Tree Traversals',
                'Binary Search Tree Operations',
                'Graph Representation and Traversal',
                'Sorting Algorithms',
                'Searching Algorithms',
                'Hashing Techniques'
            ]
            
            for i, title in enumerate(experiments, 1):
                exp = Experiment(
                    lab_config_id=lab.id,
                    experiment_no=i,
                    title=title,
                    description=f'Implementation and analysis of {title.lower()}',
                    materials_text=f'Study material for {title}',
                    total_marks=10,
                    duration_minutes=15
                )
                db.session.add(exp)
        
        db.session.commit()
        print('Seed data created successfully!')
        print('Test credentials:')
        print('  Teacher: teacher@test.com / password123')
        print('  Student: student@test.com / password123')

if __name__ == '__main__':
    seed_database()
