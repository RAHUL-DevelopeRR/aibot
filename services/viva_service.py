"""
Viva Service Module - MCQ Generation and Exam Management
Integrates Base Viva's MCQ generation logic with aibot's authentication system.
"""

import os
import requests
import json
import random
import uuid
import hashlib
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Perplexity API Configuration
PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY')
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

# In-memory store for generated questions keyed by session
# Format: {session_key: {"questions": [...], "topic": str, "created_at": datetime}}
SESSION_STORE = {}


def build_response(status: str, stage: str, data=None, message: str = ""):
    """
    Build standardized API response.
    
    Frontend must transition UI strictly based on backend stage:
    - "mcqs_ready": Questions are loaded, show MCQ interface
    - "exam_completed": Exam finished, show score
    - "error": An error occurred
    """
    return {
        "status": status,
        "stage": stage,
        "data": data or {},
        "message": message
    }


def generate_unique_seed(student_id, experiment_id):
    """
    Generate a unique seed for randomization based on student and experiment.
    Ensures each student gets a unique question/option order.
    """
    combined = f"{student_id}-{experiment_id}-{uuid.uuid4()}"
    return int(hashlib.md5(combined.encode()).hexdigest()[:8], 16)


def shuffle_options(options, seed):
    """
    Shuffle the options dictionary while maintaining correct answer tracking.
    Returns shuffled options and the new correct answer letter.
    """
    random.seed(seed)
    items = list(options.items())
    random.shuffle(items)
    
    # Reassign letters A, B, C, D to shuffled options
    letters = ['A', 'B', 'C', 'D']
    new_options = {}
    letter_mapping = {}  # Map old letter to new letter
    
    for idx, (old_letter, text) in enumerate(items):
        new_letter = letters[idx]
        new_options[new_letter] = text
        letter_mapping[old_letter] = new_letter
    
    return new_options, letter_mapping


def generate_mcq_with_perplexity(topic: str, num_questions: int = 10, difficulty: str = "medium", session_id: str = None) -> dict:
    """
    Generate MCQs - First tries Java Backend, falls back to direct Perplexity API.
    
    The Java backend is preferred because:
    - Questions are stored in database for scoring
    - Centralized AI call management
    - Better audit trail
    
    Args:
        topic: The experiment topic for MCQ generation
        num_questions: Number of questions to generate (default 10)
        difficulty: Question difficulty level
        session_id: Unique session identifier for randomization
        
    Returns:
        dict with 'questions' list or 'error' message
    """
    
    # Try Java Backend first
    try:
        from services.backend_service import get_backend_service
        backend = get_backend_service()
        
        if backend.is_enabled:
            print(f"[VivaService] Attempting Java backend for topic: {topic}")
            result = backend.create_viva(topic, num_questions, difficulty)
            
            if 'questions' in result and result['questions']:
                print(f"[VivaService] Java backend returned {len(result['questions'])} questions")
                # Apply shuffling same as before
                questions = result['questions']
                unique_id = session_id[:8] if session_id else str(uuid.uuid4())[:6]
                random.seed(generate_unique_seed(unique_id, topic))
                random.shuffle(questions)
                
                for idx, question in enumerate(questions):
                    question['id'] = idx + 1
                
                return {"questions": questions}
            elif result.get('use_fallback'):
                print(f"[VivaService] Backend unavailable, falling back to Perplexity: {result.get('error')}")
            else:
                print(f"[VivaService] Backend error: {result.get('error')}")
    except Exception as e:
        print(f"[VivaService] Backend service error: {e}, falling back to Perplexity")
    
    # Fallback to direct Perplexity API
    return _generate_mcq_direct_perplexity(topic, num_questions, difficulty, session_id)


def _generate_mcq_direct_perplexity(topic: str, num_questions: int = 10, difficulty: str = "medium", session_id: str = None) -> dict:
    """
    Generate MCQs using Perplexity API - OPTIMIZED FOR SPEED
    
    Optimizations applied:
    - Concise prompt (reduced tokens sent)
    - Lower max_tokens (2500 vs 4000)
    - Lower temperature (0.7 for faster, more consistent responses)
    - Reduced timeout (45s vs 60s)
    
    Args:
        topic: The experiment topic for MCQ generation
        num_questions: Number of questions to generate (default 10)
        difficulty: Question difficulty level
        session_id: Unique session identifier for randomization
        
    Returns:
        dict with 'questions' list or 'error' message
    """
    
    if not PERPLEXITY_API_KEY:
        return {"error": "Perplexity API key not configured"}
    
    # Minimal unique ID for variety
    unique_id = session_id[:8] if session_id else str(uuid.uuid4())[:6]
    
    # OPTIMIZED: Concise prompt - ~60% shorter than original
    prompt = f"""Generate {num_questions} MCQs for lab experiment: "{topic}"

Session: {unique_id}

Format (JSON only):
{{"questions":[{{"id":1,"question":"...","options":{{"A":"...","B":"...","C":"...","D":"..."}},"correct_answer":"A","explanation":"..."}}]}}

Rules:
- Viva-style conceptual questions about this experiment
- 4 plausible options per question, 1 correct answer
- Brief explanations
- No generic questions"""
    
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # OPTIMIZED: Reduced tokens and temperature for faster response
    payload = {
        "model": "sonar",
        "messages": [
            {
                "role": "system",
                "content": "Generate lab viva MCQs as JSON. Be concise."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7,   # Lower = faster, more consistent
        "max_tokens": 2500    # Reduced from 4000
    }
    
    try:
        # OPTIMIZED: Reduced timeout
        response = requests.post(PERPLEXITY_API_URL, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        
        result = response.json()
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        # Clean the response - remove markdown code blocks if present
        content = content.strip()
        if content.startswith('```json'):
            content = content[7:]
        if content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]
        content = content.strip()
        
        # Parse the JSON response
        mcq_data = json.loads(content)
        
        # Shuffle questions order
        questions = mcq_data.get('questions', [])
        random.seed(generate_unique_seed(unique_id, topic))
        random.shuffle(questions)
        
        # Shuffle options for each question and update correct answer
        for idx, question in enumerate(questions):
            option_seed = generate_unique_seed(unique_id, f"{topic}-{idx}")
            original_correct = question.get('correct_answer', 'A')
            new_options, letter_mapping = shuffle_options(question['options'], option_seed)
            question['options'] = new_options
            question['correct_answer'] = letter_mapping.get(original_correct, original_correct)
            question['id'] = idx + 1  # Reassign IDs after shuffle
        
        mcq_data['questions'] = questions
        return mcq_data
        
    except requests.exceptions.RequestException as e:
        print(f"[VivaService] API request failed: {e}")
        return {"error": f"API request failed: {str(e)}"}
    except json.JSONDecodeError as e:
        print(f"[VivaService] JSON parse error: {e}")
        return {"error": f"Failed to parse API response: {str(e)}", "raw_content": content[:500] if 'content' in locals() else "No content"}


def store_session_questions(session_key: str, questions: list, topic: str):
    """
    Store generated questions in session store for later scoring.
    
    Args:
        session_key: Unique key like "student_session:experiment_id"
        questions: List of question dictionaries
        topic: The topic/experiment name
    """
    SESSION_STORE[session_key] = {
        "questions": questions,
        "topic": topic,
        "created_at": datetime.utcnow()
    }
    print(f"[VivaService] Stored {len(questions)} questions for session: {session_key}")


def get_session_questions(session_key: str) -> list:
    """
    Retrieve stored questions for a session.
    
    Args:
        session_key: The session key used when storing
        
    Returns:
        List of questions or empty list if not found
    """
    session_data = SESSION_STORE.get(session_key, {})
    return session_data.get('questions', [])


def clear_session(session_key: str):
    """Remove session data after exam completion."""
    if session_key in SESSION_STORE:
        SESSION_STORE.pop(session_key, None)
        print(f"[VivaService] Cleared session: {session_key}")


def calculate_score(questions: list, answers: dict) -> dict:
    """
    Calculate score based on submitted answers.
    
    Args:
        questions: List of question dicts with correct_answer
        answers: Dict mapping question_id (str) to selected answer (A/B/C/D)
        
    Returns:
        dict with score, total, and detailed results
    """
    # Normalize answers to string keys
    normalized_answers = {str(k): v for k, v in answers.items()}
    
    score = 0
    total = len(questions)
    results = []
    
    for question in questions:
        question_id = str(question.get('id'))
        correct_answer = question.get('correct_answer')
        selected_answer = normalized_answers.get(question_id)
        
        is_correct = selected_answer and correct_answer and selected_answer == correct_answer
        if is_correct:
            score += 1
        
        results.append({
            'question_id': question_id,
            'correct_answer': correct_answer,
            'selected_answer': selected_answer,
            'is_correct': is_correct
        })
    
    return {
        'score': score,
        'total': total,
        'results': results
    }


def cleanup_expired_sessions(max_age_hours: int = 24):
    """
    Remove sessions older than max_age_hours.
    Should be called periodically to prevent memory leaks.
    """
    from datetime import timedelta
    
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    expired_keys = [
        key for key, data in SESSION_STORE.items()
        if data.get('created_at', datetime.utcnow()) < cutoff
    ]
    
    for key in expired_keys:
        SESSION_STORE.pop(key, None)
    
    if expired_keys:
        print(f"[VivaService] Cleaned up {len(expired_keys)} expired sessions")
