"""
Sync Service for fetching lab details from Google Sheets and populating the database.
"""
from typing import Optional
from services.sheets_service import get_sheets_service


def sync_experiments_from_sheets() -> dict:
    """
    Sync experiments from Google Sheets (Teacher Sheet) to the database.
    
    Expected sheet structure in 'Experiments' sheet:
    Exp No | Experiment Name | Lab Name | Description | Max Marks
    
    Expected sheet structure in 'Labs' sheet:
    Lab ID | Lab Name | Subject Code | Year | Total Experiments
    
    Returns:
        dict with 'success', 'message', and 'data' keys
    """
    from extensions import db
    from models.user import Subject, LabConfig, Experiment
    
    sheets = get_sheets_service()
    if not sheets:
        return {
            'success': False,
            'message': 'Google Sheets not configured. Set GOOGLE_SHEETS_CREDENTIALS_PATH and GOOGLE_TEACHER_SHEET_ID.',
            'data': None
        }
    
    try:
        # Get lab info from sheets
        labs_data = sheets.get_lab_info()
        experiments_data = sheets.get_experiments_list()
        
        if not labs_data:
            return {
                'success': False,
                'message': 'No labs found in Google Sheets. Ensure "Labs" sheet exists with proper format.',
                'data': None
            }
        
        if not experiments_data:
            return {
                'success': False,
                'message': 'No experiments found in Google Sheets. Ensure "Experiments" sheet exists with proper format.',
                'data': None
            }
        
        synced_labs = []
        synced_experiments = []
        
        # Process each lab
        for lab_info in labs_data:
            lab_name = lab_info.get('lab_name', '').strip()
            subject_code = lab_info.get('subject', '').strip()
            year = lab_info.get('year', 'III').strip()
            total_experiments = int(lab_info.get('total_experiments', 10))
            
            if not lab_name or not subject_code:
                continue
            
            # Find or create subject
            subject = Subject.query.filter_by(subject_code=subject_code).first()
            if not subject:
                subject = Subject(
                    subject_code=subject_code,
                    subject_name=lab_name,
                    description=f'{lab_name} - {subject_code}',
                    is_lab=True,
                    year=year
                )
                db.session.add(subject)
                db.session.flush()
            
            # Find or create lab config
            lab_config = LabConfig.query.filter_by(subject_id=subject.id, lab_name=lab_name).first()
            if not lab_config:
                lab_config = LabConfig(
                    subject_id=subject.id,
                    lab_name=lab_name,
                    description=f'Lab configuration for {lab_name}',
                    total_experiments=total_experiments
                )
                db.session.add(lab_config)
                db.session.flush()
            else:
                # Update existing
                lab_config.total_experiments = total_experiments
            
            synced_labs.append(lab_name)
            
            # Add experiments for this lab
            lab_experiments = [e for e in experiments_data if e.get('lab_name', '').strip() == lab_name]
            
            for exp_info in lab_experiments:
                try:
                    exp_no = int(exp_info.get('experiment_no', 0))
                except (ValueError, TypeError):
                    continue
                
                if exp_no < 1 or exp_no > 10:
                    continue
                
                exp_name = exp_info.get('experiment_name', '').strip()
                exp_desc = exp_info.get('description', '').strip()
                try:
                    max_marks = int(exp_info.get('max_marks', 10))
                except (ValueError, TypeError):
                    max_marks = 10
                
                if not exp_name:
                    continue
                
                # Find or create experiment
                experiment = Experiment.query.filter_by(
                    lab_config_id=lab_config.id,
                    experiment_no=exp_no
                ).first()
                
                if not experiment:
                    experiment = Experiment(
                        lab_config_id=lab_config.id,
                        experiment_no=exp_no,
                        title=exp_name,
                        description=exp_desc or f'Implementation of {exp_name}',
                        total_marks=max_marks,
                        duration_minutes=15
                    )
                    db.session.add(experiment)
                else:
                    # Update existing
                    experiment.title = exp_name
                    experiment.description = exp_desc or experiment.description
                    experiment.total_marks = max_marks
                
                synced_experiments.append(f"Exp {exp_no}: {exp_name}")
        
        db.session.commit()
        
        return {
            'success': True,
            'message': f'Synced {len(synced_labs)} labs and {len(synced_experiments)} experiments from Google Sheets.',
            'data': {
                'labs': synced_labs,
                'experiments': synced_experiments
            }
        }
        
    except Exception as e:
        db.session.rollback()
        return {
            'success': False,
            'message': f'Error syncing from Google Sheets: {str(e)}',
            'data': None
        }


def sync_teachers_from_sheets() -> dict:
    """
    Sync teachers from Google Sheets (Teacher Sheet) to the database.
    
    Expected sheet structure in 'Teachers' sheet:
    Teacher ID | Name | Email | Department | Designation | Subjects
    
    Returns:
        dict with 'success', 'message', and 'data' keys
    """
    from extensions import db
    from models.user import User
    
    sheets = get_sheets_service()
    if not sheets:
        return {
            'success': False,
            'message': 'Google Sheets not configured.',
            'data': None
        }
    
    try:
        teachers_data = sheets.get_teacher_details()
        
        if not teachers_data:
            return {
                'success': False,
                'message': 'No teachers found in Google Sheets.',
                'data': None
            }
        
        synced_teachers = []
        
        for teacher_info in teachers_data:
            email = teacher_info.get('email', '').strip()
            name = teacher_info.get('name', '').strip()
            
            if not email or not name:
                continue
            
            # Find existing teacher
            teacher = User.query.filter_by(email=email, role='teacher').first()
            
            if not teacher:
                teacher = User(
                    name=name,
                    email=email,
                    roll_number=teacher_info.get('teacher_id', ''),
                    role='teacher',
                    department=teacher_info.get('department', ''),
                    designation=teacher_info.get('designation', '')
                )
                teacher.set_password('password123')  # Default password
                db.session.add(teacher)
            else:
                # Update existing
                teacher.name = name
                teacher.department = teacher_info.get('department', '') or teacher.department
                teacher.designation = teacher_info.get('designation', '') or teacher.designation
            
            synced_teachers.append(name)
        
        db.session.commit()
        
        return {
            'success': True,
            'message': f'Synced {len(synced_teachers)} teachers from Google Sheets.',
            'data': {'teachers': synced_teachers}
        }
        
    except Exception as e:
        db.session.rollback()
        return {
            'success': False,
            'message': f'Error syncing teachers: {str(e)}',
            'data': None
        }
