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
        
        # Create a lab subject
        subject = Subject.query.filter_by(subject_code='CBB1323').first()
        if not subject:
            subject = Subject(
                subject_code='CBB1323',
                subject_name='Artificial Intelligence Laboratory',
                description='Practical implementation of AI algorithms and machine learning techniques',
                is_lab=True,
                year='III'
            )
            db.session.add(subject)
            db.session.flush()
            
            # Create lab config
            lab = LabConfig(
                subject_id=subject.id,
                lab_name='Artificial Intelligence Laboratory',
                description='Implementation of various AI algorithms including search techniques, optimization, and machine learning',
                total_experiments=10,
                materials_text='Topics include problem solving using search algorithms, heuristic techniques, optimization methods, machine learning classifiers, and chatbot development.'
            )
            db.session.add(lab)
            db.session.flush()
            
            # Create 10 experiments - AI Lab (CBB1323)
            experiments = [
                ('Implement Water Jug Problem', 'Implementation of the classic Water Jug Problem using state space search and BFS/DFS algorithms to find the solution path.'),
                ('Implement Monkey Banana Problem', 'Implementation of the Monkey Banana Problem demonstrating goal-based planning and problem solving using AI techniques.'),
                ('Implement Hill Climbing Problem', 'Implementation of Hill Climbing algorithm, a local search optimization technique for solving optimization problems.'),
                ('Implementation of Constraint Satisfaction Problem', 'Implementation of CSP solving techniques including backtracking and constraint propagation for problems like N-Queens or Map Coloring.'),
                ('Implementation of Greedy Heuristic Search Problems', 'Implementation of Greedy Best-First Search algorithm using heuristic functions for efficient pathfinding and optimization.'),
                ('Implementation of Simulated Annealing Heuristic Search', 'Implementation of Simulated Annealing algorithm, a probabilistic optimization technique inspired by the annealing process in metallurgy.'),
                ('Implementation of KNN for an application', 'Implementation of K-Nearest Neighbors algorithm for classification tasks such as iris flower classification or handwriting recognition.'),
                ('Implementation of SVM for an application', 'Implementation of Support Vector Machine algorithm for classification problems with linear and non-linear decision boundaries.'),
                ('Implementation of Decision Tree for an application', 'Implementation of Decision Tree classifier for classification tasks with visualization of the decision-making process.'),
                ('Implementation of Simple Chatbot for an application', 'Implementation of a rule-based or AI-powered chatbot using natural language processing techniques for conversational interactions.')
            ]
            
            for i, (title, description) in enumerate(experiments, 1):
                exp = Experiment(
                    lab_config_id=lab.id,
                    experiment_no=i,
                    title=title,
                    description=description,
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
