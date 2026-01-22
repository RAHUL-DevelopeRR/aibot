"""Test Perplexity API MCQ generation"""
import os
from dotenv import load_dotenv
load_dotenv()

from services.perplexity_service import generate_mcq_questions

# Test with a sample experiment
print("Testing Perplexity API MCQ Generation...")
print(f"API Key present: {bool(os.getenv('PERPLEXITY_API_KEY'))}")

questions = generate_mcq_questions(
    experiment_title='Water Jug Problem',
    experiment_description='Solve water jug problem using BFS',
    lab_name='AI Lab',
    student_id=1,
    num_questions=3
)

print(f"\nGenerated {len(questions)} Questions:")
for q in questions:
    print(f"\nQ{q['question_number']}: {q['question']}")
    for opt, text in q['options'].items():
        print(f"  {opt}) {text}")
    print(f"  Correct: {q['correct_answer']}")
