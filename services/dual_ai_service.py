"""
Dual AI Service — Combines Perplexity + Gemini for best-quality chatbot responses.

Strategy:
1. Query both APIs in parallel
2. If both succeed, synthesize into one top-quality answer using Gemini
3. If only one succeeds, use that response directly
4. If both fail, return error
"""
import os
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

logger = logging.getLogger(__name__)

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

# System prompt for the MKCE Assistant
SYSTEM_PROMPT = """You are MKCE Viva Assistant — an elite, world-class AI tutor for M. Kumarasamy College of Engineering students.

Your mission is to provide the BEST possible answers — clear, accurate, comprehensive, and educational.

Guidelines:
- Give thorough, well-structured answers with examples and explanations
- Use bullet points, numbered lists, and code blocks for clarity
- For programming topics: include code examples with comments
- For conceptual topics: explain with analogies and real-world applications
- For viva preparation: provide key points that impress examiners
- Always be encouraging and supportive
- If relevant, mention time/space complexity for algorithms
- Keep language clear but professional — suitable for engineering students"""


def _get_perplexity_key():
    key = os.getenv("PERPLEXITY_API_KEY", "").strip()
    return key if key else None


def _get_gemini_model():
    if not GEMINI_AVAILABLE:
        return None
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel('gemini-2.0-flash')
    except Exception as e:
        logger.error(f"Failed to init Gemini model: {e}")
        return None


def _call_perplexity(messages, context=None):
    """Call Perplexity API and return response text or None."""
    api_key = _get_perplexity_key()
    if not api_key:
        logger.warning("Perplexity API key not configured")
        return None

    system_message = SYSTEM_PROMPT
    if context:
        system_message += f"\n\nCurrent context: {context}"

    api_messages = [{"role": "system", "content": system_message}]
    api_messages.extend(messages)

    try:
        response = requests.post(
            PERPLEXITY_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "sonar-pro",
                "messages": api_messages,
                "max_tokens": 2048,
                "temperature": 0.5
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            text = data['choices'][0]['message']['content']
            logger.info(f"Perplexity responded ({len(text)} chars)")
            return text
        else:
            logger.error(f"Perplexity API error: {response.status_code} - {response.text[:200]}")
            return None

    except Exception as e:
        logger.error(f"Perplexity call failed: {e}")
        return None


def _call_gemini(messages, context=None):
    """Call Gemini API and return response text or None."""
    model = _get_gemini_model()
    if not model:
        logger.warning("Gemini model not available")
        return None

    system_message = SYSTEM_PROMPT
    if context:
        system_message += f"\n\nCurrent context: {context}"

    # Build conversation for Gemini
    prompt_parts = [system_message + "\n\n"]
    for msg in messages:
        role = "User" if msg['role'] == 'user' else "Assistant"
        prompt_parts.append(f"{role}: {msg['content']}\n\n")
    prompt_parts.append("Assistant: ")

    full_prompt = "".join(prompt_parts)

    try:
        response = model.generate_content(full_prompt)
        text = response.text.strip()
        logger.info(f"Gemini responded ({len(text)} chars)")
        return text
    except Exception as e:
        logger.error(f"Gemini call failed: {e}")
        return None


def _synthesize_responses(perplexity_response, gemini_response, user_question):
    """Use Gemini to synthesize both responses into one definitive answer."""
    model = _get_gemini_model()
    if not model:
        # Can't synthesize, pick the longer/better one
        if len(perplexity_response) > len(gemini_response):
            return perplexity_response
        return gemini_response

    synthesis_prompt = f"""You are an expert answer synthesizer. You have TWO responses to the same question from different AI models. Your job is to create ONE definitive, best-possible answer by combining the strengths of both.

USER QUESTION: {user_question}

--- RESPONSE A (Web-grounded, citation-backed) ---
{perplexity_response}

--- RESPONSE B (Reasoning-focused, structured) ---
{gemini_response}

INSTRUCTIONS:
- Merge the BEST parts of both responses into one comprehensive answer
- Keep the most accurate facts, best examples, and clearest explanations from each
- Use well-structured formatting (headers, bullet points, code blocks where appropriate)
- Remove any redundancy — don't repeat the same point twice
- If the responses contradict, go with the more technically accurate one
- The final answer should feel like it came from ONE expert, not a merge of two
- Do NOT mention that this is a synthesis or that there were two responses
- Keep it concise but comprehensive — quality over quantity

Write the final synthesized answer:"""

    try:
        response = model.generate_content(synthesis_prompt)
        text = response.text.strip()
        logger.info(f"Synthesis complete ({len(text)} chars)")
        return text
    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        # Fallback: return the longer response
        if len(perplexity_response) > len(gemini_response):
            return perplexity_response
        return gemini_response


def get_best_response(messages, context=None):
    """
    Query both Perplexity and Gemini in parallel, then synthesize the best answer.

    Args:
        messages: List of message dicts with 'role' and 'content'
        context: Optional context string

    Returns:
        dict with 'success', 'response' or 'error'
    """
    if not messages:
        return {'success': False, 'error': 'No messages provided'}

    # Get the latest user question for synthesis prompt
    user_question = ""
    for msg in reversed(messages):
        if msg.get('role') == 'user':
            user_question = msg['content']
            break

    perplexity_result = None
    gemini_result = None

    # Call both APIs in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(_call_perplexity, messages, context): 'perplexity',
            executor.submit(_call_gemini, messages, context): 'gemini'
        }

        for future in as_completed(futures):
            source = futures[future]
            try:
                result = future.result()
                if source == 'perplexity':
                    perplexity_result = result
                else:
                    gemini_result = result
            except Exception as e:
                logger.error(f"{source} future failed: {e}")

    logger.info(f"Results — Perplexity: {'✓' if perplexity_result else '✗'}, Gemini: {'✓' if gemini_result else '✗'}")

    # Decision logic
    if perplexity_result and gemini_result:
        # Both succeeded — synthesize the best answer
        logger.info("Both APIs succeeded — synthesizing best answer")
        final_response = _synthesize_responses(perplexity_result, gemini_result, user_question)
        return {'success': True, 'response': final_response}

    elif perplexity_result:
        # Only Perplexity succeeded
        logger.info("Using Perplexity response (Gemini failed)")
        return {'success': True, 'response': perplexity_result}

    elif gemini_result:
        # Only Gemini succeeded
        logger.info("Using Gemini response (Perplexity failed)")
        return {'success': True, 'response': gemini_result}

    else:
        # Both failed
        logger.error("Both Perplexity and Gemini failed")
        return {
            'success': False,
            'error': 'AI service temporarily unavailable. Please try again.'
        }
