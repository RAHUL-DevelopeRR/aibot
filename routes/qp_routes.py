"""
Question Paper Generator Blueprint
===================================
Ported from QP/academicgen-engine/server.py into the Viva aibot.
Provides API endpoints for AI question generation + Word doc export.
All routes are prefixed with /qp/
"""

from flask import Blueprint, request, jsonify, render_template, send_file, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps
import os
import io
import json
import re
import base64
import requests

qp_bp = Blueprint('qp', __name__, url_prefix='/qp')


# =========================================================================
# AUTH DECORATOR
# =========================================================================

def teacher_required(f):
    """Decorator for teacher-only routes"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'teacher':
            return redirect(url_for('teacher.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# =========================================================================
# PERPLEXITY / GEMINI API CONFIGURATION
# =========================================================================

PERPLEXITY_API_URL = 'https://api.perplexity.ai/chat/completions'
GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent'

SYSTEM_PROMPT = """You are an expert academic question paper generator for M. Kumarasamy College of Engineering, following Anna University exam patterns strictly.

🌐 WEB-ASSISTED CONTENT FETCHING (ENABLED)
You are allowed and encouraged to search the web for:
- Anna University previous year question papers
- University question banks and exam archives
- Educational websites and open course materials
- Standard textbook problems and examples
- Public lecture notes with diagram-based problems

RULES FOR WEB USAGE:
1. Use web content for reference and structure only - adapt and reframe to match syllabus
2. Do NOT copy questions verbatim - rewrite with original phrasing
3. Ensure fetched content matches the given unit boundaries and cognitive level
4. Do NOT include URLs, citations, or source names in generated questions

📐 DIAGRAM-BASED QUESTION RULES
When a topic requires visualization, you MUST include diagram-based questions:
- Data Structures: Binary trees, AVL trees, B+ trees, heaps, graphs, linked lists
- Operating Systems: Process state diagrams, paging/segmentation, Gantt charts, disk scheduling
- DBMS: ER diagrams, relational schemas, B+ trees, precedence graphs, normalization diagrams
- Computer Networks: OSI layers, network topologies, timing diagrams, packet formats
- Algorithms: Recursion trees, state space trees, flowcharts, DP tables
- Compiler Design: NFA/DFA diagrams, parse trees, syntax trees, flow graphs
- AI: Game trees, search trees, neural network diagrams, decision trees

DIAGRAM QUESTION REQUIREMENTS:
1. Only 1-2 Part B questions should require diagram interaction (not mandatory)
2. Diagram questions must include clear instructions (e.g., "Draw and label the AVL tree after inserting...")
3. Include traversal/execution/analysis tasks with diagrams
4. Provide structured diagram descriptions for complex visualizations

🎯 BLOOM'S TAXONOMY COGNITIVE LEVELS
Match questions to the required level:
- BTL1 (Remember): Define, List, State, Identify, Draw basic diagrams
- BTL2 (Understand): Explain, Describe, Illustrate with diagram, Compare
- BTL3 (Apply): Solve, Calculate, Trace algorithm, Construct diagram step-by-step
- BTL4 (Analyze): Analyze, Deduce, Compare with justification, Detect properties from diagram
- BTL5 (Evaluate): Evaluate, Validate, Optimize, Assess with reasoning
- BTL6 (Create): Design, Formulate, Synthesize, Create new solution

CRITICAL RULES:
1. Questions must be academically rigorous and examination-appropriate
2. Each question must have clear CO (Course Outcome) and BTL (Bloom's Taxonomy Level) mapping
3. Generate questions strictly from the provided syllabus topics ONLY
4. Never create questions outside the given unit boundaries
5. Ensure variety in question types with emphasis on diagram-based and problem-solving
6. Match the difficulty distribution specified in the template"""


# =========================================================================
# API KEY HELPERS
# =========================================================================

def get_api_key():
    """Get Perplexity API key from environment."""
    # Try both env var names
    api_key = os.environ.get('API_KEY') or os.environ.get('PERPLEXITY_API_KEY')
    if not api_key:
        raise ValueError("API_KEY / PERPLEXITY_API_KEY not configured in environment")
    return api_key


def get_gemini_api_key():
    """Get Gemini API key from environment."""
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("⚠️ GEMINI_API_KEY not configured - falling back to Perplexity only")
        return None
    return api_key


# =========================================================================
# AI API CALL FUNCTIONS
# =========================================================================

def call_gemini_api(prompt: str, use_web_search: bool = False) -> str:
    """Call Gemini API with the given prompt. Supports web search via Google Search grounding."""
    api_key = get_gemini_api_key()
    if not api_key:
        return None

    url = f"{GEMINI_API_URL}?key={api_key}"
    headers = {'Content-Type': 'application/json'}

    payload = {
        'contents': [{
            'parts': [{'text': f"{SYSTEM_PROMPT}\n\n{prompt}"}]
        }],
        'generationConfig': {
            'temperature': 0.4,
            'maxOutputTokens': 16000,
        }
    }

    if use_web_search:
        payload['tools'] = [{'googleSearch': {}}]

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=180)
        response.raise_for_status()
        data = response.json()
        if 'candidates' in data and len(data['candidates']) > 0:
            candidate = data['candidates'][0]
            if 'content' in candidate and 'parts' in candidate['content']:
                return candidate['content']['parts'][0].get('text', '')
        print(f"⚠️ Gemini API returned unexpected format: {data}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Gemini API error: {e}")
        return None
    except Exception as e:
        print(f"⚠️ Gemini API unexpected error: {e}")
        return None


def call_perplexity_api(prompt: str) -> str:
    """Call Perplexity API with the given prompt."""
    api_key = get_api_key()
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': 'sonar',
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.4,
        'max_tokens': 16000,
    }
    response = requests.post(PERPLEXITY_API_URL, json=payload, headers=headers, timeout=180)
    response.raise_for_status()
    data = response.json()
    return data['choices'][0]['message']['content']


def call_combined_api(prompt: str, use_web_search: bool = False) -> str:
    """
    Call both Gemini and Perplexity APIs and combine responses.
    - Gemini: 70% weight (primary)
    - Perplexity: 30% weight (supplementary)
    - For diagram questions: Use only Gemini with web search
    """
    gemini_response = None
    perplexity_response = None

    try:
        gemini_response = call_gemini_api(prompt, use_web_search=use_web_search)
        if gemini_response:
            print("✅ Gemini API responded successfully")
    except Exception as e:
        print(f"⚠️ Gemini failed: {e}")

    if use_web_search and gemini_response:
        return gemini_response

    try:
        perplexity_response = call_perplexity_api(prompt)
        if perplexity_response:
            print("✅ Perplexity API responded successfully")
    except Exception as e:
        print(f"⚠️ Perplexity failed: {e}")

    if gemini_response and not perplexity_response:
        return gemini_response
    if perplexity_response and not gemini_response:
        return perplexity_response
    if gemini_response:
        return gemini_response
    return perplexity_response


# =========================================================================
# JSON PARSING HELPERS
# =========================================================================

def extract_json(text: str) -> str:
    """Extract JSON from AI response - improved parsing with truncation handling."""
    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
    if json_match:
        return repair_json(json_match.group(1).strip())

    start_idx = text.find('[')
    if start_idx != -1:
        bracket_count = 0
        last_complete_idx = start_idx
        for i, char in enumerate(text[start_idx:], start_idx):
            if char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    return repair_json(text[start_idx:i+1])
            if char == '}' and bracket_count == 1:
                last_complete_idx = i
        if bracket_count > 0 and last_complete_idx > start_idx:
            partial_json = text[start_idx:last_complete_idx+1] + ']'
            print(f"⚠️ JSON was truncated, recovered {partial_json.count('{')//2} questions")
            return repair_json(partial_json)

    start_idx = text.find('{')
    if start_idx != -1:
        brace_count = 0
        for i, char in enumerate(text[start_idx:], start_idx):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    return repair_json(text[start_idx:i+1])
        if brace_count > 0:
            partial_json = text[start_idx:] + '}' * brace_count
            return repair_json(partial_json)

    return text


def repair_json(json_str: str) -> str:
    """Repair common JSON formatting issues from AI responses."""
    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        pass

    json_str = re.sub(r'\}\s*\{', '},{', json_str)
    json_str = re.sub(r'"\s*\n\s*"', '",\n"', json_str)
    json_str = re.sub(r'"\s+("[\w]+":)', r'", \1', json_str)
    json_str = re.sub(r',\s*\]', ']', json_str)
    json_str = re.sub(r',\s*\}', '}', json_str)
    json_str = re.sub(r'(true|false|\d+)\s*\n\s*"', r'\1,\n"', json_str)
    json_str = re.sub(r'"\s*\n\s*"(\w+)":', r'",\n"\1":', json_str)
    return json_str


def get_cia_constraints(faculty_selection: dict) -> str:
    """Get CIA-specific constraints for prompt."""
    cia_type = faculty_selection.get('ciaType', 'CIA-I')
    qp_type = faculty_selection.get('qpType', 'QP-I')

    unit_constraint = ('Unit I and Unit II ONLY' if cia_type == 'CIA-I'
                      else 'Unit III and Unit IV ONLY')
    co_constraint = ('CO1 and CO2 ONLY' if cia_type == 'CIA-I'
                    else 'CO3 and CO4 ONLY')

    if qp_type == 'QP-I':
        pattern_constraint = """QP Type I Pattern (Total 60 marks):
- Part A: 6 questions × 2 marks = 12 marks (BTL 2-3)
- Part B: 4 question pairs with OR choice × 12 marks = 48 marks (BTL 3-5)"""
    else:
        pattern_constraint = """QP Type II Pattern (Total 60 marks):
- Part A: 6 questions × 2 marks = 12 marks (BTL 2-3)
- Part B: 2 question pairs with OR choice × 16 marks = 32 marks (BTL 3-5)
- Part C: 1 question pair with OR choice × 16 marks = 16 marks (BTL 4-5)"""

    return f"""MANDATORY CONSTRAINTS:
1. Questions MUST be from: {unit_constraint}
2. Course Outcomes MUST be: {co_constraint}
3. {pattern_constraint}"""


# =========================================================================
# PAGE ROUTES
# =========================================================================

@qp_bp.route('/')
@teacher_required
def qp_home():
    """Serve the Question Paper Generator SPA page."""
    return render_template('teacher/question_paper.html')


# =========================================================================
# API ENDPOINTS
# =========================================================================

@qp_bp.route('/api/health', methods=['GET'])
@login_required
def health_check():
    """Health check endpoint."""
    api_key = os.environ.get('API_KEY') or os.environ.get('PERPLEXITY_API_KEY')
    return jsonify({
        "status": "ok",
        "message": "QP Generator is running",
        "api_configured": bool(api_key)
    })


@qp_bp.route('/api/generate-bank', methods=['POST'])
@teacher_required
def generate_bank():
    """Generate question bank via AI APIs."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        cdap = data.get('cdap', '')
        syllabus = data.get('syllabus', '')
        template = data.get('template', '')
        faculty_selection = data.get('facultySelection', {})

        constraints = get_cia_constraints(faculty_selection)
        cia_type = faculty_selection.get('ciaType', 'CIA-I')
        units = [1, 2] if cia_type == 'CIA-I' else [3, 4]
        cos = ['CO1', 'CO2'] if cia_type == 'CIA-I' else ['CO3', 'CO4']

        prompt = f"""INPUTS:

[CDAP]
{cdap}

[SYLLABUS]
{syllabus}

[TEMPLATE]
{template}

{constraints}

TASK:
Generate a Question Bank for {cia_type} with exactly 20 questions total.
Return ONLY a valid JSON array of objects with NO markdown formatting.

QUESTION DISTRIBUTION:
- Part A (2 marks): 10 questions (5 per CO)
- Part B (12/16 marks): 10 questions (5 per CO)

REQUIREMENTS:
1. Include 2-3 diagram-based questions
2. Include 3-4 numerical/problem-solving questions
3. Mix difficulty levels appropriately

STRICT RULES:
- Only use Units: {', '.join(map(str, units))}
- Only use COs: {', '.join(cos)}

QUESTION TYPES BY BTL LEVEL:
- BTL1 (Remember): Definition, Match the following, Formula recall, Diagram labeling, Tabulate, Identify from a drawing, Description
- BTL2 (Understand): Classification, Compare/Contrast/Differentiate, Examine/Explain, Give examples, Identify modification and justify, Use Cases, Real-time application
- BTL3 (Apply): Application problem, Case Study, Experimental arrangement, Divide system into use and justify, Identify by describing application
- BTL4 (Analyze): Analysis with validation, Deduce steps for application, Case study analysis, Deconstruct experiment, Modification to solve
- BTL5 (Evaluate): Analyze system and component, Write conclusions from comparison, Review/Test/Validate, Evaluate design and explain, Problem evaluation with results
- BTL6 (Create): Design new system, Hypothesis formulation, Integrate and formulate design, Synthesize and justify design

Each question object must have these exact fields:
{{
  "id": "string (unique identifier like Q1, Q2, etc.)",
  "text": "string (the question text - for diagram questions include specific drawing instructions)",
  "marks": number (2 for Part A, 12 or 16 for Part B/C),
  "unit": number ({' or '.join(map(str, units))} ONLY),
  "topic": "string",
  "subtopic": "string",
  "co": "string ({' or '.join(cos)} ONLY)",
  "btl": "string (BTL1, BTL2, BTL3, BTL4, BTL5, or BTL6)",
  "difficulty": "Easy" | "Medium" | "Hard",
  "type": "string (must be one of the types listed above matching the BTL level)",
  "hasDiagram": boolean (true if question requires drawing/analyzing a diagram),
  "diagramType": "string (e.g., 'Binary Tree', 'ER Diagram', 'Flowchart', 'State Diagram', 'Graph', 'Table', 'Timing Diagram', 'None')",
  "diagramDescription": "string (brief description of the diagram to be drawn, or 'N/A' if no diagram)"
}}

Return ONLY the JSON array, no explanation or markdown."""

        result = call_combined_api(prompt)
        json_str = extract_json(result)
        questions = json.loads(json_str)
        return jsonify({"questions": questions})

    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except requests.exceptions.Timeout:
        return jsonify({"error": "Request timed out. Please try again."}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"AI service error: {str(e)}"}), 500
    except json.JSONDecodeError:
        return jsonify({"error": "Failed to parse AI response"}), 500
    except Exception as e:
        print(f"Error in generate_bank: {e}")
        return jsonify({"error": "Failed to generate question bank"}), 500


@qp_bp.route('/api/generate-paper', methods=['POST'])
@teacher_required
def generate_paper():
    """Generate formatted question paper text."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        bank = data.get('bank', [])
        template = data.get('template', '')
        syllabus = data.get('syllabus', '')
        faculty_selection = data.get('facultySelection', {})

        cia_type = faculty_selection.get('ciaType', 'CIA-I')
        qp_type = faculty_selection.get('qpType', 'QP-I')
        course_code = faculty_selection.get('courseCode', '')
        course_title = faculty_selection.get('courseTitle', '')
        cia_label = 'CIA-1' if cia_type == 'CIA-I' else 'CIA-2'

        bank_json = json.dumps(bank)

        if qp_type == 'QP-I':
            co1 = 'CO1' if cia_type == 'CIA-I' else 'CO3'
            co2 = 'CO2' if cia_type == 'CIA-I' else 'CO4'
            part_b_pattern = f"""
============================================================
PART -B (4X12 MARKS = 48 MARKS)
============================================================

Q.NO    Question                                              CO    BTL   MARKS
7.a     [Question]                                            {co1}   BTL3   12
                              (OR)
7.b     [Alternative]                                         {co1}   BTL3   12
8.a     [Question]                                            {co1}   BTL3   12
                              (OR)
8.b     [Alternative]                                         {co1}   BTL4   12
9.a     [Question]                                            {co2}   BTL3   12
                              (OR)
9.b     [Alternative]                                         {co2}   BTL4   12
10.a    [Question]                                            {co2}   BTL4   12
                              (OR)
10.b    [Alternative]                                         {co2}   BTL3   12"""
        else:
            co1 = 'CO1' if cia_type == 'CIA-I' else 'CO3'
            co2 = 'CO2' if cia_type == 'CIA-I' else 'CO4'
            part_b_pattern = f"""
============================================================
PART -B (2X16 MARKS = 32 MARKS)
============================================================

Q.NO    Question                                              CO    BTL   MARKS
7.a     [Question]                                            {co1}   BTL3   16
                              (OR)
7.b     [Alternative]                                         {co1}   BTL4   16
8.a     [Question]                                            {co2}   BTL4   16
                              (OR)
8.b     [Alternative]                                         {co2}   BTL3   16

============================================================
PART -C (1X16 MARKS = 16 MARKS)
============================================================

Q.NO    Question                                              CO    BTL   MARKS
9.a     [Application/Analysis question]                       {co1}   BTL4   16
                              (OR)
9.b     [Alternative]                                         {co2}   BTL5   16"""

        prompt = f"""TASK:
Generate a final formatted Question Paper based on the Question Bank provided.

[TEMPLATE RULES]
{template}

[QUESTION BANK]
{bank_json}

[REQUIRED FORMAT]
Generate the question paper with header and body:

================================================================================
                        M.Kumarasamy College of Engineering
                        NAAC Accredited Autonomous Institution
================================================================================

                                    {cia_label}

REG No: |___|___|___|___|___|___|___|___|___|___|___|___|

DEPARTMENT: [From syllabus]    SEMESTER: [e.g. IV]
SECTION: [e.g. A]              DATE & SESSION: [YYYY-MM-DD (FN)]
DURATION: 120 Minutes          MAX MARKS: 60
COURSE CODE & NAME: {course_code} - {course_title}

============================================================
PART -A (6X2 MARKS = 12 MARKS)
============================================================

Q.NO    Question                                              CO    BTL   MARKS
1.      [Question]                                            {co1}   BTL2    2
2.      [Question]                                            {co1}   BTL2    2
3.      [Question]                                            {co1}   BTL2    2
4.      [Question]                                            {co2}   BTL3    2
5.      [Question]                                            {co2}   BTL2    2
6.      [Question]                                            {co2}   BTL2    2

{part_b_pattern}

Output ONLY the formatted paper, no JSON."""

        result = call_perplexity_api(prompt)
        return jsonify({"paper": result})

    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Error in generate_paper: {e}")
        return jsonify({"error": "Failed to generate paper"}), 500


@qp_bp.route('/api/generate-paper-data', methods=['POST'])
@teacher_required
def generate_paper_data():
    """Generate structured question paper data for Word document."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        bank = data.get('bank', [])
        template = data.get('template', '')
        syllabus = data.get('syllabus', '')
        faculty_selection = data.get('facultySelection', {})

        cia_type = faculty_selection.get('ciaType', 'CIA-I')
        qp_type = faculty_selection.get('qpType', 'QP-I')
        course_code = faculty_selection.get('courseCode', '')
        course_title = faculty_selection.get('courseTitle', '')

        cos = ['CO1', 'CO2'] if cia_type == 'CIA-I' else ['CO3', 'CO4']
        bank_json = json.dumps(bank)

        if qp_type == 'QP-I':
            structure_desc = f'''"partBQuestions": [
    {{"qno": "7.(a)", "question": "...", "co": "{cos[0]}", "btl": "BTL3", "marks": "12"}},
    {{"qno": "(OR)", "question": "(OR)", "co": "", "btl": "", "marks": ""}},
    {{"qno": "7.(b)", "question": "...", "co": "{cos[0]}", "btl": "BTL3", "marks": "12"}},
    {{"qno": "8.(a)", "question": "...", "co": "{cos[0]}", "btl": "BTL3", "marks": "12"}},
    {{"qno": "(OR)", "question": "(OR)", "co": "", "btl": "", "marks": ""}},
    {{"qno": "8.(b)", "question": "...", "co": "{cos[0]}", "btl": "BTL4", "marks": "12"}},
    {{"qno": "9.(a)", "question": "...", "co": "{cos[1]}", "btl": "BTL3", "marks": "12"}},
    {{"qno": "(OR)", "question": "(OR)", "co": "", "btl": "", "marks": ""}},
    {{"qno": "9.(b)", "question": "...", "co": "{cos[1]}", "btl": "BTL4", "marks": "12"}},
    {{"qno": "10.(a)", "question": "...", "co": "{cos[1]}", "btl": "BTL3", "marks": "12"}},
    {{"qno": "(OR)", "question": "(OR)", "co": "", "btl": "", "marks": ""}},
    {{"qno": "10.(b)", "question": "...", "co": "{cos[1]}", "btl": "BTL3", "marks": "12"}}
]'''
        else:
            structure_desc = f'''"partBQuestions": [
    {{"qno": "7.(a)", "question": "...", "co": "{cos[0]}", "btl": "BTL3", "marks": "16"}},
    {{"qno": "(OR)", "question": "(OR)", "co": "", "btl": "", "marks": ""}},
    {{"qno": "7.(b)", "question": "...", "co": "{cos[0]}", "btl": "BTL4", "marks": "16"}},
    {{"qno": "8.(a)", "question": "...", "co": "{cos[1]}", "btl": "BTL4", "marks": "16"}},
    {{"qno": "(OR)", "question": "(OR)", "co": "", "btl": "", "marks": ""}},
    {{"qno": "8.(b)", "question": "...", "co": "{cos[1]}", "btl": "BTL3", "marks": "16"}}
],
"partCQuestions": [
    {{"qno": "9.(a)", "question": "...", "co": "{cos[0]}", "btl": "BTL4", "marks": "16"}},
    {{"qno": "(OR)", "question": "(OR)", "co": "", "btl": "", "marks": ""}},
    {{"qno": "9.(b)", "question": "...", "co": "{cos[1]}", "btl": "BTL5", "marks": "16"}}
]'''

        prompt = f"""TASK:
Generate structured question paper data as JSON for Word document generation.

[TEMPLATE RULES]
{template}

[SYLLABUS]
{syllabus}

[QUESTION BANK]
{bank_json}

[INSTRUCTIONS]
1. Use course code: {course_code}, course name: {course_title}
2. CIA Type: {cia_type}, QP Type: {qp_type}
3. ONLY use COs: {', '.join(cos)}
4. Select 6 questions for Part A (2 marks each)
5. {'Select 8 questions for Part B (4 pairs with OR, 12 marks each)' if qp_type == 'QP-I' else 'Select 4 for Part B (16 marks) + 2 for Part C (16 marks)'}
6. Return ONLY valid JSON with NO markdown
7. For OR rows: {{"qno": "(OR)", "question": "(OR)", "co": "", "btl": "", "marks": ""}}
8. Question numbers: 7.(a), 7.(b), 8.(a), 8.(b), etc.
9. IMPORTANT: For Part B and Part C questions, include diagram fields:
   - hasDiagram: true/false (true if question involves a diagram in any way)
   - diagramType: "Gantt Chart", "Binary Tree", "Graph", "State Diagram", "ER Diagram", "Flowchart", "Table", "Parse Tree", "DFA/NFA", or "None"
   - diagramDescription: Brief description (e.g., "Binary tree with nodes A,B,C,D,E")
   - diagramRole: "input" or "output"
     * "input" = Question PROVIDES a diagram for student to analyze
     * "output" = Student DRAWS the diagram
10. At most 1-2 Part B questions should have hasDiagram: true

Return JSON object with this structure:
{{
  "department": "CSE",
  "section": "A",
  "semester": "IV",
  "dateSession": "2025-02-27 (FN)",
  "courseCode": "{course_code}",
  "courseName": "{course_title}",
  "ciaType": "{cia_type}",
  "qpType": "{qp_type}",
  "partAQuestions": [
    {{"qno": "1.", "question": "...", "co": "{cos[0]}", "btl": "BTL2", "marks": "2"}},
    {{"qno": "2.", "question": "...", "co": "{cos[0]}", "btl": "BTL2", "marks": "2"}},
    {{"qno": "3.", "question": "...", "co": "{cos[0]}", "btl": "BTL2", "marks": "2"}},
    {{"qno": "4.", "question": "...", "co": "{cos[1]}", "btl": "BTL2", "marks": "2"}},
    {{"qno": "5.", "question": "...", "co": "{cos[1]}", "btl": "BTL2", "marks": "2"}},
    {{"qno": "6.", "question": "...", "co": "{cos[1]}", "btl": "BTL2", "marks": "2"}}
  ],
  {structure_desc}
}}

Return ONLY the JSON, no explanation."""

        result = call_perplexity_api(prompt)
        json_str = extract_json(result)
        paper_data = json.loads(json_str)
        return jsonify({"paperData": paper_data})

    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Error in generate_paper_data: {e}")
        return jsonify({"error": "Failed to generate paper data"}), 500


@qp_bp.route('/api/generate-docx', methods=['POST'])
@teacher_required
def generate_docx():
    """Generate a Word document from question data."""
    try:
        from IDLE import create_exam_paper

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        department = data.get('department', 'CSBS')
        section_val = data.get('section', 'A')
        semester = data.get('semester', 'IV')
        date_session = data.get('dateSession', '2025-02-27 (FN)')
        course_code = data.get('courseCode', 'CBB1222')
        course_name = data.get('courseName', 'Operating Systems')
        cia_type = data.get('ciaType', 'CIA-I')
        qp_type = data.get('qpType', 'QP-I')
        part_a_questions = data.get('partAQuestions', None)
        part_b_questions = data.get('partBQuestions', None)
        part_c_questions = data.get('partCQuestions', None)

        doc_bytes = create_exam_paper(
            department=department,
            section_val=section_val,
            semester=semester,
            date_session=date_session,
            course_code=course_code,
            course_name=course_name,
            cia_type=cia_type,
            qp_type=qp_type,
            part_a_questions=part_a_questions,
            part_b_questions=part_b_questions,
            part_c_questions=part_c_questions
        )

        filename = f"CIA_Paper_{course_code}_{cia_type}_{qp_type}.docx"
        return send_file(
            io.BytesIO(doc_bytes),
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        print(f"Error generating document: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@qp_bp.route('/api/generate-diagram', methods=['POST'])
@teacher_required
def generate_diagram():
    """Generate SVG diagram based on diagram type and description."""
    try:
        data = request.get_json()
        diagram_type = data.get('diagramType', 'Generic')
        description = data.get('description', '')

        svg_templates = {
            'Gantt Chart': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 150">
                <rect fill="#f8f9fa" width="400" height="150"/>
                <text x="200" y="20" text-anchor="middle" font-size="12" font-weight="bold">Gantt Chart</text>
                <line x1="50" y1="35" x2="50" y2="130" stroke="#333" stroke-width="2"/>
                <line x1="50" y1="130" x2="380" y2="130" stroke="#333" stroke-width="2"/>
                <rect x="60" y="45" width="80" height="20" fill="#4CAF50" rx="3"/>
                <text x="100" y="59" text-anchor="middle" font-size="9" fill="white">P1</text>
                <rect x="140" y="70" width="60" height="20" fill="#2196F3" rx="3"/>
                <text x="170" y="84" text-anchor="middle" font-size="9" fill="white">P2</text>
                <rect x="200" y="95" width="100" height="20" fill="#FF9800" rx="3"/>
                <text x="250" y="109" text-anchor="middle" font-size="9" fill="white">P3</text>
                <text x="60" y="145" font-size="8">0</text>
                <text x="140" y="145" font-size="8">4</text>
                <text x="200" y="145" font-size="8">7</text>
                <text x="300" y="145" font-size="8">12</text>
            </svg>''',
            'Binary Tree': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 200">
                <rect fill="#f8f9fa" width="300" height="200"/>
                <text x="150" y="20" text-anchor="middle" font-size="12" font-weight="bold">Binary Tree</text>
                <line x1="150" y1="55" x2="90" y2="95" stroke="#333" stroke-width="2"/>
                <line x1="150" y1="55" x2="210" y2="95" stroke="#333" stroke-width="2"/>
                <line x1="90" y1="115" x2="60" y2="155" stroke="#333" stroke-width="2"/>
                <line x1="90" y1="115" x2="120" y2="155" stroke="#333" stroke-width="2"/>
                <circle cx="150" cy="45" r="18" fill="#4CAF50"/>
                <text x="150" y="50" text-anchor="middle" font-size="12" fill="white">50</text>
                <circle cx="90" cy="105" r="18" fill="#2196F3"/>
                <text x="90" y="110" text-anchor="middle" font-size="12" fill="white">30</text>
                <circle cx="210" cy="105" r="18" fill="#2196F3"/>
                <text x="210" y="110" text-anchor="middle" font-size="12" fill="white">70</text>
                <circle cx="60" cy="165" r="15" fill="#FF9800"/>
                <text x="60" y="169" text-anchor="middle" font-size="10" fill="white">20</text>
                <circle cx="120" cy="165" r="15" fill="#FF9800"/>
                <text x="120" y="169" text-anchor="middle" font-size="10" fill="white">40</text>
            </svg>''',
            'Graph': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 200">
                <rect fill="#f8f9fa" width="300" height="200"/>
                <text x="150" y="20" text-anchor="middle" font-size="12" font-weight="bold">Graph</text>
                <line x1="80" y1="70" x2="150" y2="50" stroke="#333" stroke-width="2"/>
                <line x1="150" y1="50" x2="220" y2="70" stroke="#333" stroke-width="2"/>
                <line x1="80" y1="70" x2="80" y2="140" stroke="#333" stroke-width="2"/>
                <line x1="220" y1="70" x2="220" y2="140" stroke="#333" stroke-width="2"/>
                <line x1="80" y1="140" x2="150" y2="170" stroke="#333" stroke-width="2"/>
                <line x1="220" y1="140" x2="150" y2="170" stroke="#333" stroke-width="2"/>
                <circle cx="150" cy="50" r="18" fill="#4CAF50"/>
                <text x="150" y="55" text-anchor="middle" font-size="12" fill="white">A</text>
                <circle cx="80" cy="70" r="18" fill="#2196F3"/>
                <text x="80" y="75" text-anchor="middle" font-size="12" fill="white">B</text>
                <circle cx="220" cy="70" r="18" fill="#2196F3"/>
                <text x="220" y="75" text-anchor="middle" font-size="12" fill="white">C</text>
                <circle cx="80" cy="140" r="18" fill="#FF9800"/>
                <text x="80" y="145" text-anchor="middle" font-size="12" fill="white">D</text>
                <circle cx="220" cy="140" r="18" fill="#FF9800"/>
                <text x="220" y="145" text-anchor="middle" font-size="12" fill="white">E</text>
                <circle cx="150" cy="170" r="18" fill="#9C27B0"/>
                <text x="150" y="175" text-anchor="middle" font-size="12" fill="white">F</text>
            </svg>''',
            'State Diagram': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 150">
                <rect fill="#f8f9fa" width="400" height="150"/>
                <text x="200" y="20" text-anchor="middle" font-size="12" font-weight="bold">Process State Diagram</text>
                <ellipse cx="60" cy="80" rx="35" ry="25" fill="#4CAF50"/>
                <text x="60" y="85" text-anchor="middle" font-size="10" fill="white">New</text>
                <ellipse cx="160" cy="80" rx="35" ry="25" fill="#2196F3"/>
                <text x="160" y="85" text-anchor="middle" font-size="10" fill="white">Ready</text>
                <ellipse cx="260" cy="80" rx="35" ry="25" fill="#FF9800"/>
                <text x="260" y="85" text-anchor="middle" font-size="10" fill="white">Running</text>
                <ellipse cx="360" cy="80" rx="35" ry="25" fill="#f44336"/>
                <text x="360" y="85" text-anchor="middle" font-size="10" fill="white">Exit</text>
            </svg>''',
            'ER Diagram': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 350 180">
                <rect fill="#f8f9fa" width="350" height="180"/>
                <text x="175" y="20" text-anchor="middle" font-size="12" font-weight="bold">ER Diagram</text>
                <rect x="30" y="60" width="80" height="40" fill="#4CAF50" rx="3"/>
                <text x="70" y="85" text-anchor="middle" font-size="11" fill="white">Student</text>
                <rect x="240" y="60" width="80" height="40" fill="#4CAF50" rx="3"/>
                <text x="280" y="85" text-anchor="middle" font-size="11" fill="white">Course</text>
                <polygon points="175,60 205,80 175,100 145,80" fill="#2196F3"/>
                <text x="175" y="85" text-anchor="middle" font-size="9" fill="white">Enrolls</text>
                <line x1="110" y1="80" x2="145" y2="80" stroke="#333" stroke-width="2"/>
                <line x1="205" y1="80" x2="240" y2="80" stroke="#333" stroke-width="2"/>
            </svg>''',
            'Flowchart': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 250">
                <rect fill="#f8f9fa" width="200" height="250"/>
                <text x="100" y="20" text-anchor="middle" font-size="12" font-weight="bold">Flowchart</text>
                <ellipse cx="100" cy="45" rx="35" ry="15" fill="#4CAF50"/>
                <text x="100" y="50" text-anchor="middle" font-size="10" fill="white">Start</text>
                <rect x="60" y="75" width="80" height="30" fill="#2196F3" rx="3"/>
                <text x="100" y="95" text-anchor="middle" font-size="10" fill="white">Process</text>
                <polygon points="100,120 140,145 100,170 60,145" fill="#FF9800"/>
                <text x="100" y="150" text-anchor="middle" font-size="9" fill="white">Decision</text>
                <ellipse cx="100" cy="235" rx="35" ry="15" fill="#f44336"/>
                <text x="100" y="240" text-anchor="middle" font-size="10" fill="white">End</text>
            </svg>''',
            'Table': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 150">
                <rect fill="#f8f9fa" width="300" height="150"/>
                <text x="150" y="20" text-anchor="middle" font-size="12" font-weight="bold">Data Table</text>
                <rect x="30" y="35" width="240" height="25" fill="#4CAF50"/>
                <text x="70" y="52" text-anchor="middle" font-size="10" fill="white">Process</text>
                <text x="130" y="52" text-anchor="middle" font-size="10" fill="white">Burst</text>
                <text x="190" y="52" text-anchor="middle" font-size="10" fill="white">Arrival</text>
                <text x="250" y="52" text-anchor="middle" font-size="10" fill="white">Priority</text>
            </svg>'''
        }

        svg = svg_templates.get(diagram_type)
        if not svg:
            svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 150">
                <rect fill="#f0f4f8" width="300" height="150" rx="8"/>
                <rect x="10" y="10" width="280" height="130" fill="white" stroke="#e2e8f0" stroke-width="2" stroke-dasharray="8,4" rx="5"/>
                <text x="150" y="50" text-anchor="middle" font-size="14" font-weight="bold" fill="#4a5568">{diagram_type}</text>
                <text x="150" y="80" text-anchor="middle" font-size="10" fill="#718096">{description[:50]}...</text>
                <text x="150" y="120" text-anchor="middle" font-size="9" fill="#a0aec0">[Diagram to be drawn by student]</text>
            </svg>'''

        svg_bytes = svg.encode('utf-8')
        b64 = base64.b64encode(svg_bytes).decode('utf-8')
        data_url = f"data:image/svg+xml;base64,{b64}"
        return jsonify({"imageUrl": data_url, "diagramType": diagram_type})

    except Exception as e:
        print(f"Error generating diagram: {e}")
        return jsonify({"error": str(e)}), 500
