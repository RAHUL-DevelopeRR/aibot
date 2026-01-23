from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime

from extensions import db
from models.user import StudentAnswer, VivaSession, LabConfig, Experiment
from services.perplexity_service import evaluate_mcq_answers
from services.sheets_service import get_sheets_service

api_bp = Blueprint('api', __name__)


@api_bp.route('/viva/<int:viva_session_id>/submit-answer', methods=['POST'])
@login_required
def submit_answer(viva_session_id):
    """Submit answer to a question - handles MCQ answers"""
    try:
        data = request.get_json()
        
        viva = VivaSession.query.get_or_404(viva_session_id)
        
        if viva.student_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        question_number = data.get('question_number')
        answer_text = data.get('answer_text')
        
        if not all([question_number, answer_text]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Validate MCQ answer format (single letter)
        if not isinstance(answer_text, str) or len(answer_text) > 1:
            return jsonify({'error': 'Invalid answer format. Expected single letter (A/B/C/D)'}), 400
        
        existing_answer = StudentAnswer.query.filter_by(
            viva_session_id=viva_session_id,
            question_number=question_number
        ).first()
        
        if existing_answer:
            existing_answer.answer_text = answer_text
            existing_answer.updated_at = datetime.utcnow()  # ✅ Now works - field exists
        else:
            new_answer = StudentAnswer(
                viva_session_id=viva_session_id,
                question_number=question_number,
                answer_text=answer_text,
                created_at=datetime.utcnow()  # ✅ Now works - field exists
            )
            db.session.add(new_answer)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Answer saved successfully',
            'question_number': question_number
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/viva/<int:viva_session_id>/get-answer/<int:question_number>', methods=['GET'])
@login_required
def get_answer(viva_session_id, question_number):
    """Get saved answer for a question"""
    try:
        viva = VivaSession.query.get_or_404(viva_session_id)
        
        if viva.student_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        answer = StudentAnswer.query.filter_by(
            viva_session_id=viva_session_id,
            question_number=question_number
        ).first()
        
        if answer:
            return jsonify({
                'success': True,
                'question_number': question_number,
                'answer_text': answer.answer_text
            }), 200
        else:
            return jsonify({
                'success': True,
                'question_number': question_number,
                'answer_text': ''
            }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/viva/<int:viva_session_id>/submit', methods=['POST'])
@login_required
def submit_viva(viva_session_id):
    """Submit completed viva - evaluates MCQ answers and calculates marks"""
    try:
        viva = VivaSession.query.get_or_404(viva_session_id)
        
        if viva.student_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        if viva.status in ['completed', 'violated']:
            return jsonify({'error': 'Viva already submitted'}), 400
        
        # Get all student answers
        answers = StudentAnswer.query.filter_by(viva_session_id=viva_session_id).all()
        student_answers = {a.question_number: a.answer_text for a in answers}
        
        # Evaluate answers against generated questions
        questions = viva.generated_questions or []
        
        if questions:
            result = evaluate_mcq_answers(questions, student_answers)
            viva.obtained_marks = result['obtained_marks']
            
            # Update individual answer marks
            for r in result['results']:
                ans = next((a for a in answers if a.question_number == r['question_number']), None)
                if ans:
                    ans.marks_obtained = r['marks']
        else:
            # Fallback: count answered questions
            viva.obtained_marks = len(answers)
        
        viva.status = 'completed'
        viva.completed_at = datetime.utcnow()
        
        db.session.commit()
        
        # Write marks to Google Sheets (Single Source of Truth)
        sheets = get_sheets_service()
        if sheets and viva.experiment and current_user.roll_number:
            try:
                success = sheets.update_student_experiment_mark(
                    reg_no=current_user.roll_number,
                    experiment_no=viva.experiment.experiment_no,
                    marks=viva.obtained_marks
                )
                if success:
                    print(f"Marks updated in Google Sheets: {current_user.roll_number} Exp_{viva.experiment.experiment_no} = {viva.obtained_marks}")
            except Exception as sheet_error:
                print(f"Google Sheets sync error: {sheet_error}")
        
        return jsonify({
            'success': True,
            'message': 'Viva submitted successfully',
            'obtained_marks': viva.obtained_marks,
            'total_marks': viva.total_marks
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/viva/<int:viva_session_id>/progress', methods=['GET'])
@login_required
def get_viva_progress(viva_session_id):
    """Get viva progress"""
    try:
        viva = VivaSession.query.get_or_404(viva_session_id)
        
        if viva.student_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        total_questions = len(viva.generated_questions) if viva.generated_questions else 10
        
        answered_count = StudentAnswer.query.filter_by(
            viva_session_id=viva_session_id
        ).count()
        
        return jsonify({
            'success': True,
            'total_questions': total_questions,
            'answered_questions': answered_count,
            'progress_percentage': (answered_count / total_questions * 100) if total_questions > 0 else 0
        }), 200
    
    except Exception as e:
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
        reason = data.get('reason', 'Tab switch or window blur detected')
        
        viva.violation_count = (viva.violation_count or 0) + 1
        viva.finalize_violation(reason)
        db.session.commit()
        
        # Write 0 marks to Google Sheets
        sheets = get_sheets_service()
        if sheets and viva.experiment and current_user.roll_number:
            try:
                sheets.update_student_experiment_mark(
                    reg_no=current_user.roll_number,
                    experiment_no=viva.experiment.experiment_no,
                    marks=0
                )
            except Exception as sheet_error:
                print(f"Google Sheets sync error: {sheet_error}")
        
        return jsonify({
            'success': True,
            'message': 'Violation recorded. Viva finalized with 0 marks.',
            'violation_reason': reason
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/labs', methods=['GET'])
@login_required
def get_labs():
    """Get all labs"""
    try:
        subject_id = request.args.get('subject_id', type=int)
        
        query = LabConfig.query
        
        if subject_id:
            query = query.filter_by(subject_id=subject_id)
        
        labs = query.all()
        
        labs_data = [{
            'id': lab.id,
            'lab_name': lab.lab_name,
            'subject_id': lab.subject_id,
            'description': lab.description,
            'total_marks': lab.total_marks
        } for lab in labs]
        
        return jsonify({
            'success': True,
            'labs': labs_data
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
