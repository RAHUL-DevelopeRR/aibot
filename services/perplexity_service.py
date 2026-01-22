"""Perplexity AI Service for Chatbot functionality"""
import requests
import json
import logging
import os

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"


def get_chat_response(messages, context=None):
    """
    Get a response from Perplexity AI
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        context: Optional context about the viva/lab for more relevant responses
    
    Returns:
        dict with 'success', 'response' or 'error'
    """
    try:
        # Build system message with context
        system_message = """You are an intelligent AI assistant for the Lab Viva Assistant platform. 
You help students prepare for their lab viva examinations by:
- Explaining concepts related to their experiments
- Answering questions about data structures, algorithms, and programming
- Providing practice questions and explanations
- Giving tips for viva preparation
- Clarifying doubts about lab experiments

Be helpful, educational, and encouraging. Keep responses concise but informative."""

        if context:
            system_message += f"\n\nCurrent context: {context}"

        # Prepare the API request
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }

        # Build messages list with system prompt
        api_messages = [{"role": "system", "content": system_message}]
        api_messages.extend(messages)

        payload = {
            "model": "sonar",
            "messages": api_messages,
            "max_tokens": 1024,
            "temperature": 0.7
        }

        logger.debug(f"Sending request to Perplexity API with model: {payload['model']}")
        
        response = requests.post(
            PERPLEXITY_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )

        logger.debug(f"Perplexity API response status: {response.status_code}")
        logger.debug(f"Perplexity API response: {response.text[:500]}")

        if response.status_code == 200:
            data = response.json()
            assistant_message = data['choices'][0]['message']['content']
            return {
                'success': True,
                'response': assistant_message
            }
        else:
            return {
                'success': False,
                'error': f"API Error: {response.status_code} - {response.text}"
            }

    except requests.exceptions.Timeout:
        return {
            'success': False,
            'error': "Request timed out. Please try again."
        }
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'error': f"Network error: {str(e)}"
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }


def get_viva_help(experiment_title, question):
    """
    Get help specifically for a viva experiment
    
    Args:
        experiment_title: Name of the experiment
        question: Student's question
    
    Returns:
        dict with 'success', 'response' or 'error'
    """
    context = f"The student is preparing for a viva on: {experiment_title}"
    messages = [{"role": "user", "content": question}]
    return get_chat_response(messages, context)


def generate_practice_questions(topic, count=5):
    """
    Generate practice questions for a topic
    
    Args:
        topic: The topic to generate questions for
        count: Number of questions to generate
    
    Returns:
        dict with 'success', 'questions' or 'error'
    """
    messages = [{
        "role": "user",
        "content": f"Generate {count} viva practice questions about '{topic}'. Format as a numbered list with brief expected answers."
    }]
    
    result = get_chat_response(messages)
    if result['success']:
        return {
            'success': True,
            'questions': result['response']
        }
    return result


def generate_mcq_questions(experiment_title, experiment_description, lab_name, student_id, num_questions=10):
    """
    Generate random MCQ questions for viva using Perplexity API.
    
    Args:
        experiment_title: Title of the experiment
        experiment_description: Description of the experiment
        lab_name: Name of the lab
        student_id: Student ID (used for randomization)
        num_questions: Number of MCQs to generate (default 10)
    
    Returns:
        List of MCQ dicts with structure:
        {
            'question_number': int,
            'question': str,
            'options': {'A': str, 'B': str, 'C': str, 'D': str},
            'correct_answer': str
        }
    """
    import random
    
    prompt = f"""Generate exactly {num_questions} unique multiple choice questions (MCQs) for a lab viva assessment.

Lab: {lab_name}
Experiment: {experiment_title}
Description: {experiment_description or 'General concepts related to the experiment'}

Requirements:
1. Generate exactly {num_questions} MCQ questions
2. Each question should test understanding of the experiment concepts
3. Each question should have exactly 4 options (A, B, C, D)
4. Only ONE option should be correct
5. Questions should be of moderate difficulty (1 mark each)
6. Mix conceptual, procedural, and application-based questions
7. Make questions unique using seed {student_id}

Return ONLY a valid JSON array with this exact structure (no markdown, no explanation, no extra text):
[
    {{
        "question_number": 1,
        "question": "Question text here?",
        "options": {{
            "A": "Option A text",
            "B": "Option B text",
            "C": "Option C text",
            "D": "Option D text"
        }},
        "correct_answer": "A"
    }}
]"""

    try:
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": "You are an expert lab viva examiner. Generate MCQ questions in valid JSON format only. No markdown, no explanation."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 4096,
            "temperature": 0.8
        }

        response = requests.post(
            PERPLEXITY_API_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

        if response.status_code == 200:
            data = response.json()
            response_text = data['choices'][0]['message']['content'].strip()
            
            # Clean up response if it has markdown code blocks
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])
            
            # Remove any "json" prefix
            if response_text.startswith('json'):
                response_text = response_text[4:].strip()
            
            questions = json.loads(response_text)
            
            # Validate and fix structure
            if isinstance(questions, list):
                for i, q in enumerate(questions):
                    q['question_number'] = i + 1
                    if 'correct_answer' not in q or q['correct_answer'] not in ['A', 'B', 'C', 'D']:
                        q['correct_answer'] = 'A'
                return questions[:num_questions]
        
        # Fallback if API fails
        return _generate_fallback_mcqs(experiment_title, num_questions)
        
    except Exception as e:
        logger.error(f"Perplexity MCQ generation error: {e}")
        return _generate_fallback_mcqs(experiment_title, num_questions)


def _generate_fallback_mcqs(experiment_title, num_questions):
    """Generate simple fallback MCQs if API fails"""
    import random
    questions = []
    for i in range(num_questions):
        questions.append({
            'question_number': i + 1,
            'question': f'Question {i+1} about {experiment_title}?',
            'options': {
                'A': 'Option A',
                'B': 'Option B',
                'C': 'Option C',
                'D': 'Option D'
            },
            'correct_answer': random.choice(['A', 'B', 'C', 'D'])
        })
    return questions


def evaluate_mcq_answers(questions, student_answers):
    """
    Evaluate student MCQ answers against correct answers.
    
    Args:
        questions: List of question dicts with correct_answer
        student_answers: Dict mapping question_number to student's answer (A/B/C/D)
    
    Returns:
        {
            'total_marks': int,
            'obtained_marks': int,
            'results': [{'question_number': int, 'correct_answer': str, 'student_answer': str, 'is_correct': bool, 'marks': int}]
        }
    """
    results = []
    obtained_marks = 0
    
    for q in questions:
        q_num = q['question_number']
        correct = q['correct_answer']
        student_ans = student_answers.get(q_num, '')
        is_correct = student_ans.upper() == correct.upper() if student_ans else False
        marks = 1 if is_correct else 0
        obtained_marks += marks
        
        results.append({
            'question_number': q_num,
            'correct_answer': correct,
            'student_answer': student_ans,
            'is_correct': is_correct,
            'marks': marks
        })
    
    return {
        'total_marks': len(questions),
        'obtained_marks': obtained_marks,
        'results': results
    }
