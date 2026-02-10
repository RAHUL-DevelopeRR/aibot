"""
Backend Service Module - Java Backend API Integration
Connects Flask frontend to the Java Spring Boot backend for MCQ generation and viva management.
"""

import os
import requests
from flask import current_app
from functools import lru_cache
from datetime import datetime, timedelta


class BackendService:
    """Client for Java Backend API"""
    
    def __init__(self):
        self._token = None
        self._token_expiry = None
    
    @property
    def base_url(self):
        """Get backend API base URL from config"""
        return current_app.config.get('BACKEND_API_URL', 'http://localhost:8080')
    
    @property
    def is_enabled(self):
        """Check if Java backend is enabled"""
        return current_app.config.get('USE_JAVA_BACKEND', True)
    
    def _get_headers(self, with_auth=False):
        """Get request headers, optionally with JWT token"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if with_auth and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers
    
    def _is_token_valid(self):
        """Check if current token is still valid"""
        if not self._token or not self._token_expiry:
            return False
        return datetime.utcnow() < self._token_expiry
    
    def authenticate(self, email: str, password: str, role: str = "TEACHER") -> dict:
        """
        Authenticate with the Java backend and get JWT token.
        
        Args:
            email: User email
            password: User password
            role: User role (TEACHER, STUDENT, ADMIN)
            
        Returns:
            dict with 'token' on success or 'error' on failure
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/login",
                json={"email": email, "password": password, "role": role},
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self._token = data.get('token')
                # Token expires in 24 hours, we'll refresh at 23 hours
                self._token_expiry = datetime.utcnow() + timedelta(hours=23)
                return {"success": True, "token": self._token, "user": data.get('user')}
            else:
                return {"error": f"Authentication failed: {response.status_code}"}
                
        except requests.exceptions.RequestException as e:
            print(f"[BackendService] Auth error: {e}")
            return {"error": f"Backend connection failed: {str(e)}"}
    
    def authenticate_service(self) -> bool:
        """
        Authenticate as service account (using predefined teacher account).
        This is used for server-to-server MCQ generation calls.
        """
        # Use teacher account for MCQ generation
        service_email = os.getenv('BACKEND_SERVICE_EMAIL', 'teacher@labviva.com')
        service_password = os.getenv('BACKEND_SERVICE_PASSWORD', 'teacher123')
        
        result = self.authenticate(service_email, service_password)
        return result.get('success', False)
    
    def ensure_authenticated(self):
        """Ensure we have a valid token, authenticate if needed"""
        if not self._is_token_valid():
            return self.authenticate_service()
        return True
    
    def health_check(self) -> dict:
        """Check if backend is healthy"""
        try:
            response = requests.get(
                f"{self.base_url}/api/health",
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            return {"status": "DOWN", "error": f"Status: {response.status_code}"}
        except requests.exceptions.RequestException as e:
            return {"status": "DOWN", "error": str(e)}
    
    def login_student(self, reg_no: str, password: str) -> dict:
        """
        Authenticate a student using registration number.
        
        Args:
            reg_no: Student registration number (e.g., "927623BCB012")
            password: Student password
            
        Returns:
            dict with user info and token on success, or error message
        """
        try:
            normalized_reg_no = reg_no.upper().strip()
            
            response = requests.post(
                f"{self.base_url}/api/auth/login",
                json={
                    "regNo": normalized_reg_no,
                    "password": password,
                    "role": "STUDENT"
                },
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "token": data.get("token"),
                    "user_id": data.get("userId"),
                    "name": data.get("name"),
                    "email": data.get("email"),
                    "reg_no": data.get("regNo"),
                    "role": "student"
                }
            else:
                error_msg = "Invalid credentials"
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", error_msg)
                except:
                    pass
                return {"success": False, "error": error_msg}
                
        except requests.exceptions.RequestException as e:
            print(f"[BackendService] Student login error: {e}")
            return {"success": False, "error": f"Backend unavailable: {str(e)}"}
    
    def login_teacher(self, email: str, password: str) -> dict:
        """
        Authenticate a teacher/faculty using email.
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/login",
                json={"email": email, "password": password, "role": "TEACHER"},
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "token": data.get("token"),
                    "user_id": data.get("userId"),
                    "name": data.get("name"),
                    "email": data.get("email"),
                    "role": "teacher"
                }
            else:
                return {"success": False, "error": "Invalid credentials"}
                
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Backend unavailable: {str(e)}"}
    
    def register_student(self, reg_no: str, name: str, password: str, email: str = None) -> dict:
        """Register a new student via Java backend."""
        try:
            normalized_reg_no = reg_no.upper().strip()
            if not email:
                email = f"{normalized_reg_no.lower()}@mkce.ac.in"
            
            response = requests.post(
                f"{self.base_url}/api/auth/register",
                json={
                    "regNo": normalized_reg_no,
                    "name": name,
                    "email": email,
                    "password": password,
                    "role": "STUDENT"
                },
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "token": data.get("token"),
                    "user_id": data.get("userId"),
                    "name": data.get("name"),
                    "email": data.get("email"),
                    "reg_no": data.get("regNo"),
                    "role": "student"
                }
            else:
                error_msg = "Registration failed"
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", error_msg)
                except:
                    pass
                return {"success": False, "error": error_msg}
                
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Backend unavailable: {str(e)}"}
    
    def create_viva(self, topic: str, num_questions: int = 10, difficulty: str = "medium") -> dict:
        """
        Generate MCQs via the Java backend using the simple /api/mcq/generate endpoint.
        
        Args:
            topic: The experiment/topic name
            num_questions: Number of questions (default 10)
            difficulty: Question difficulty level
            
        Returns:
            dict with 'questions' list or 'error'
        """
        if not self.is_enabled:
            return {"error": "Java backend is disabled", "use_fallback": True}
        
        # No auth required for MCQ generation endpoint
        try:
            print(f"[BackendService] Calling /api/mcq/generate for topic: {topic}")
            response = requests.post(
                f"{self.base_url}/api/mcq/generate",
                json={
                    "topic": topic,
                    "questionCount": num_questions,
                    "difficulty": difficulty.lower()
                },
                headers=self._get_headers(),
                timeout=60  # AI generation can take time
            )
            
            if response.status_code == 200:
                data = response.json()
                questions = data.get('questions', [])
                print(f"[BackendService] Received {len(questions)} questions from Java backend")
                return {"questions": self._transform_questions(questions)}
            else:
                error_body = response.text[:200]
                print(f"[BackendService] MCQ generation failed: {response.status_code} - {error_body}")
                return {"error": f"MCQ generation failed: {response.status_code}", "use_fallback": True}
                
        except requests.exceptions.Timeout:
            print("[BackendService] Timeout during MCQ generation")
            return {"error": "Backend timeout", "use_fallback": True}
        except requests.exceptions.RequestException as e:
            print(f"[BackendService] Request error: {e}")
            return {"error": str(e), "use_fallback": True}
    
    def get_viva_questions(self, viva_id: int) -> dict:
        """
        Get questions for an existing viva.
        
        Args:
            viva_id: The viva ID from the backend
            
        Returns:
            dict with 'questions' list or 'error'
        """
        if not self.ensure_authenticated():
            return {"error": "Backend authentication failed"}
        
        try:
            response = requests.post(
                f"{self.base_url}/api/student/vivas/{viva_id}/start",
                headers=self._get_headers(with_auth=True),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {"questions": self._transform_questions(data.get('questions', []))}
            else:
                return {"error": f"Failed to get questions: {response.status_code}"}
                
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def submit_answers(self, attempt_id: int, answers: dict) -> dict:
        """
        Submit answers to the backend for scoring.
        
        Args:
            attempt_id: The attempt ID from starting a viva
            answers: Dict mapping question_id to selected answer
            
        Returns:
            dict with score information or error
        """
        if not self.ensure_authenticated():
            return {"error": "Backend authentication failed"}
        
        try:
            response = requests.post(
                f"{self.base_url}/api/student/attempts/{attempt_id}/submit",
                json={"answers": answers},
                headers=self._get_headers(with_auth=True),
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Submission failed: {response.status_code}"}
                
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def _transform_questions(self, backend_questions: list) -> list:
        """
        Transform backend question format to match existing frontend format.
        
        Backend format:
        {
            "id": 1,
            "questionText": "...",
            "optionA": "...",
            "optionB": "...",
            "optionC": "...",
            "optionD": "...",
            "correctAnswer": "A",
            "explanation": "..."
        }
        
        Frontend format:
        {
            "id": 1,
            "question": "...",
            "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
            "correct_answer": "A",
            "explanation": "..."
        }
        """
        transformed = []
        for q in backend_questions:
            transformed.append({
                "id": q.get("id"),
                "question": q.get("questionText", q.get("question", "")),
                "options": {
                    "A": q.get("optionA", q.get("options", {}).get("A", "")),
                    "B": q.get("optionB", q.get("options", {}).get("B", "")),
                    "C": q.get("optionC", q.get("options", {}).get("C", "")),
                    "D": q.get("optionD", q.get("options", {}).get("D", ""))
                },
                "correct_answer": q.get("correctAnswer", q.get("correct_answer", "A")),
                "explanation": q.get("explanation", "")
            })
        return transformed


# Singleton instance
_backend_service = None

def get_backend_service() -> BackendService:
    """Get or create the backend service singleton"""
    global _backend_service
    if _backend_service is None:
        _backend_service = BackendService()
    return _backend_service
