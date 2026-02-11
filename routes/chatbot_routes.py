"""Chatbot API routes"""
from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from services.dual_ai_service import get_best_response
from services.perplexity_service import get_viva_help, generate_practice_questions

chatbot_bp = Blueprint('chatbot', __name__)


@chatbot_bp.route('/chat', methods=['POST'])
@login_required
def chat():
    """Handle chat messages"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    messages = data.get('messages', [])
    context = data.get('context', None)
    
    if not messages:
        return jsonify({'success': False, 'error': 'No messages provided'}), 400
    
    # Get best response from dual AI (Perplexity + Gemini)
    result = get_best_response(messages, context)
    
    if result['success']:
        return jsonify({
            'success': True,
            'response': result['response']
        })
    else:
        return jsonify({
            'success': False,
            'error': result['error']
        }), 500


@chatbot_bp.route('/viva-help', methods=['POST'])
@login_required
def viva_help():
    """Get help for a specific viva experiment"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    experiment_title = data.get('experiment_title', '')
    question = data.get('question', '')
    
    if not question:
        return jsonify({'success': False, 'error': 'No question provided'}), 400
    
    result = get_viva_help(experiment_title, question)
    
    if result['success']:
        return jsonify({
            'success': True,
            'response': result['response']
        })
    else:
        return jsonify({
            'success': False,
            'error': result['error']
        }), 500


@chatbot_bp.route('/practice-questions', methods=['POST'])
@login_required
def practice_questions():
    """Generate practice questions for a topic"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    topic = data.get('topic', '')
    count = data.get('count', 5)
    
    if not topic:
        return jsonify({'success': False, 'error': 'No topic provided'}), 400
    
    result = generate_practice_questions(topic, count)
    
    if result['success']:
        return jsonify({
            'success': True,
            'questions': result['questions']
        })
    else:
        return jsonify({
            'success': False,
            'error': result['error']
        }), 500


@chatbot_bp.route('/widget')
@login_required
def chatbot_widget():
    """Render the chatbot widget page (for iframe or standalone)"""
    return render_template('chatbot/widget.html')
