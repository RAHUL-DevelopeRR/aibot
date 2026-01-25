"""Perplexity AI Service for MCQ generation and chatbot functionality"""
import requests
import json
import logging
import os
import hashlib
import time
import random

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"


def _get_api_key():
    """Get API key lazily to ensure .env is loaded"""
    key = os.getenv("PERPLEXITY_API_KEY")
    if key:
        # Remove any whitespace/newlines from key
        key = key.strip().replace('\n', '').replace('\r', '')
    return key


def get_chat_response(messages, context=None):
    """
    Get a response from Perplexity AI
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        context: Optional context about the viva/lab for more relevant responses
    
    Returns:
        dict with 'success', 'response' or 'error'
    """
    api_key = _get_api_key()
    
    if not api_key:
        logger.error("PERPLEXITY_API_KEY not set in environment")
        return {
            'success': False,
            'error': "AI service not configured. Please contact administrator."
        }
    
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
            "Authorization": f"Bearer {api_key}",
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
    Each call generates UNIQUE questions per student per attempt.
    
    Args:
        experiment_title: Title of the experiment
        experiment_description: Description of the experiment
        lab_name: Name of the lab
        student_id: Student ID (used for randomization with MD5 hash)
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
    # Generate unique seed using MD5 hash of student_id + timestamp
    # This ensures unique questions for each student but consistent within same second
    timestamp = str(int(time.time()))
    hash_input = f"{student_id}_{experiment_title}_{timestamp}".encode()
    md5_hash = hashlib.md5(hash_input).hexdigest()
    unique_seed = int(md5_hash[:8], 16)  # Use first 8 hex chars as seed
    
    # Add randomness
    random.seed(unique_seed)
    
    logger.info(f"Generating MCQs with seed {unique_seed} for student_id={student_id}, experiment={experiment_title}")
    
    # Check if API key is configured using lazy loader
    api_key = _get_api_key()
    if not api_key:
        logger.error("PERPLEXITY_API_KEY not set - using fallback questions")
        return _generate_fallback_mcqs(experiment_title, num_questions)
    
    prompt = f"""Generate exactly {num_questions} UNIQUE and DIFFERENT multiple choice questions (MCQs) for a lab viva assessment.

Lab: {lab_name}
Experiment: {experiment_title}
Description: {experiment_description or 'General concepts related to the experiment'}

CRITICAL REQUIREMENTS:
1. Generate exactly {num_questions} MCQ questions - each must be DIFFERENT and UNIQUE
2. Questions must test deep understanding of the experiment
3. Each question must have exactly 4 options (A, B, C, D)
4. Only ONE option should be correct for each question
5. Difficulty: moderate to challenging (1 mark each)
6. Mix: 40% conceptual, 30% procedural, 30% application-based
7. RANDOMIZATION SEED: {unique_seed} - use this to ensure unique questions per student
8. Do NOT repeat questions - this is student {student_id}'s unique assessment
9. Include questions about: core concepts, algorithms, implementation details, edge cases

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
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": "You are an expert lab viva examiner. Generate unique MCQ questions in valid JSON format only. No markdown, no explanation. Each generation must produce completely different questions based on the seed provided."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 4096,
            "temperature": 1.0  # Higher temperature for more randomness
        }

        logger.info(f"Calling Perplexity API for MCQ generation - student_id={student_id}, experiment={experiment_title}")
        
        response = requests.post(
            PERPLEXITY_API_URL,
            headers=headers,
            json=payload,
            timeout=60
        )
        
        logger.info(f"Perplexity API response status: {response.status_code}")

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
            if isinstance(questions, list) and len(questions) > 0:
                validated_questions = []
                for i, q in enumerate(questions):
                    if isinstance(q, dict) and 'question' in q and 'options' in q:
                        q['question_number'] = i + 1
                        if 'correct_answer' not in q or q['correct_answer'] not in ['A', 'B', 'C', 'D']:
                            q['correct_answer'] = random.choice(['A', 'B', 'C', 'D'])
                        validated_questions.append(q)
                
                if len(validated_questions) >= num_questions:
                    logger.info(f"Successfully generated {len(validated_questions)} unique MCQ questions via Perplexity")
                    return validated_questions[:num_questions]
                else:
                    logger.warning(f"Only got {len(validated_questions)} valid questions, need {num_questions}")
        
        # API returned but parsing failed
        logger.error(f"Failed to parse Perplexity response")
        return _generate_fallback_mcqs(experiment_title, num_questions)
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in MCQ generation: {e}")
        return _generate_fallback_mcqs(experiment_title, num_questions)
    except requests.exceptions.Timeout:
        logger.error("Perplexity API timeout during MCQ generation")
        return _generate_fallback_mcqs(experiment_title, num_questions)
    except requests.exceptions.RequestException as e:
        logger.error(f"Perplexity API request error: {e}")
        return _generate_fallback_mcqs(experiment_title, num_questions)
    except Exception as e:
        logger.error(f"Unexpected error in MCQ generation: {e}")
        return _generate_fallback_mcqs(experiment_title, num_questions)


def _generate_fallback_mcqs(experiment_title, num_questions):
    """Generate contextual fallback MCQs if API fails - uses experiment-specific templates"""
    
    # Experiment-specific question templates
    experiment_templates = {
        'water jug': [
            {'q': 'What is the state space representation in the Water Jug Problem?', 'a': 'A', 'opts': {'A': 'A tuple (x, y) representing water in each jug', 'B': 'Total water in system', 'C': 'Number of operations performed', 'D': 'Capacity of jugs'}},
            {'q': 'Which algorithm is commonly used to solve the Water Jug Problem?', 'a': 'B', 'opts': {'A': 'Dynamic Programming', 'B': 'BFS/DFS', 'C': 'Greedy Algorithm', 'D': 'Divide and Conquer'}},
            {'q': 'What is the goal state in Water Jug Problem?', 'a': 'C', 'opts': {'A': 'Both jugs empty', 'B': 'Both jugs full', 'C': 'Desired amount in one jug', 'D': 'Equal water in both jugs'}},
            {'q': 'How many operations are possible in Water Jug Problem?', 'a': 'D', 'opts': {'A': '2', 'B': '3', 'C': '4', 'D': '6 (fill, empty, pour for each jug)'}},
            {'q': 'What type of search is Water Jug Problem?', 'a': 'A', 'opts': {'A': 'State space search', 'B': 'Linear search', 'C': 'Binary search', 'D': 'Interpolation search'}},
        ],
        'default': [
            {'q': f'What is the primary objective of {experiment_title}?', 'a': 'A', 'opts': {'A': 'To understand and implement the core algorithm', 'B': 'To memorize the code', 'C': 'To copy from textbook', 'D': 'None of the above'}},
            {'q': f'What is the time complexity typically analyzed in {experiment_title}?', 'a': 'B', 'opts': {'A': 'Space complexity only', 'B': 'Worst, average, and best case', 'C': 'Only best case', 'D': 'Not applicable'}},
            {'q': 'What is an algorithm?', 'a': 'A', 'opts': {'A': 'Step-by-step procedure to solve a problem', 'B': 'A programming language', 'C': 'A type of data structure', 'D': 'A hardware component'}},
            {'q': 'What does Big-O notation represent?', 'a': 'C', 'opts': {'A': 'Best case complexity', 'B': 'Average case complexity', 'C': 'Upper bound of complexity', 'D': 'Lower bound of complexity'}},
            {'q': 'Which data structure uses LIFO principle?', 'a': 'B', 'opts': {'A': 'Queue', 'B': 'Stack', 'C': 'Array', 'D': 'Linked List'}},
        ]
    }
    
    # Find matching template
    template_key = 'default'
    title_lower = experiment_title.lower()
    for key in experiment_templates.keys():
        if key in title_lower:
            template_key = key
            break
    
    templates = experiment_templates[template_key]
    questions = []
    
    random.shuffle(templates)
    for i in range(num_questions):
        if i < len(templates):
            t = templates[i]
            questions.append({
                'question_number': i + 1,
                'question': t['q'],
                'options': t['opts'],
                'correct_answer': t['a']
            })
        else:
            questions.append({
                'question_number': i + 1,
                'question': f'What is a key consideration in {experiment_title}?',
                'options': {
                    'A': 'Algorithm correctness',
                    'B': 'Time efficiency',
                    'C': 'Space efficiency',
                    'D': 'All of the above'
                },
                'correct_answer': 'D'
            })
    
    logger.warning(f"Using fallback MCQs for {experiment_title}")
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
