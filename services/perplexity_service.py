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
