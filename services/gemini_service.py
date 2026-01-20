"""
Gemini API Service for MCQ generation and evaluation
Uses environment variable GEMINI_API_KEY for authentication
"""
import os
import json
import random
import google.generativeai as genai
from typing import List, Dict, Optional


class GeminiService:
    """Service for generating and evaluating MCQ questions using Gemini API"""
    
    def __init__(self):
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
    
    def generate_mcq_questions(
        self, 
        experiment_title: str, 
        experiment_description: str,
        materials_text: str,
        lab_name: str,
        student_id: int,
        num_questions: int = 10
    ) -> List[Dict]:
        """
        Generate unique MCQ questions for a student based on experiment materials.
        
        Returns list of dicts with structure:
        {
            'question_number': int,
            'question': str,
            'options': {'A': str, 'B': str, 'C': str, 'D': str},
            'correct_answer': str  # 'A', 'B', 'C', or 'D'
        }
        """
        prompt = f"""You are an expert lab viva examiner. Generate exactly {num_questions} unique multiple choice questions (MCQs) for a lab viva assessment.

Lab: {lab_name}
Experiment: {experiment_title}
Description: {experiment_description}

Materials/Context:
{materials_text if materials_text else 'General laboratory concepts related to the experiment.'}

Requirements:
1. Generate exactly {num_questions} MCQ questions
2. Each question should test understanding of the experiment concepts
3. Each question should have exactly 4 options (A, B, C, D)
4. Only ONE option should be correct
5. Questions should be of moderate difficulty (1 mark each)
6. Mix conceptual, procedural, and application-based questions
7. Use seed value {student_id} to ensure questions are different for each student

Return ONLY a valid JSON array with this exact structure (no markdown, no explanation):
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
    }},
    ...
]
"""
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Clean up response if it has markdown code blocks
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1])
            
            questions = json.loads(response_text)
            
            # Validate structure
            if not isinstance(questions, list) or len(questions) != num_questions:
                raise ValueError(f"Expected {num_questions} questions, got {len(questions) if isinstance(questions, list) else 'non-list'}")
            
            for i, q in enumerate(questions):
                q['question_number'] = i + 1
                if 'options' not in q or not isinstance(q['options'], dict):
                    raise ValueError(f"Question {i+1} missing options")
                if 'correct_answer' not in q or q['correct_answer'] not in ['A', 'B', 'C', 'D']:
                    raise ValueError(f"Question {i+1} has invalid correct_answer")
            
            return questions
            
        except json.JSONDecodeError as e:
            # Fallback: generate simple questions
            return self._generate_fallback_questions(experiment_title, num_questions)
        except Exception as e:
            print(f"Gemini API error: {e}")
            return self._generate_fallback_questions(experiment_title, num_questions)
    
    def _generate_fallback_questions(self, experiment_title: str, num_questions: int) -> List[Dict]:
        """Generate simple fallback questions if Gemini fails"""
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
    
    def evaluate_answers(
        self,
        questions: List[Dict],
        student_answers: Dict[int, str]
    ) -> Dict:
        """
        Evaluate student answers against correct answers.
        
        Args:
            questions: List of question dicts with correct_answer
            student_answers: Dict mapping question_number to student's answer (A/B/C/D)
        
        Returns:
            {
                'total_marks': int,
                'obtained_marks': int,
                'results': [
                    {
                        'question_number': int,
                        'correct_answer': str,
                        'student_answer': str,
                        'is_correct': bool,
                        'marks': int
                    }
                ]
            }
        """
        results = []
        obtained_marks = 0
        
        for q in questions:
            q_num = q['question_number']
            correct = q['correct_answer']
            student_ans = student_answers.get(q_num, '')
            is_correct = student_ans.upper() == correct.upper()
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


# Singleton instance
_gemini_service = None

def get_gemini_service() -> GeminiService:
    """Get or create Gemini service instance"""
    global _gemini_service
    if _gemini_service is None:
        try:
            _gemini_service = GeminiService()
        except ValueError as e:
            print(f"Warning: {e}")
            return None
    return _gemini_service
