"""
Google Sheets Service for student roster and marks synchronization.

Requirements:
1. Set environment variable GOOGLE_SHEETS_CREDENTIALS_PATH to path of service account JSON
2. Set environment variable GOOGLE_SHEET_ID to the Sheet ID
3. Share the Google Sheet with the service account email
"""
import os
import json
from typing import List, Dict, Optional
from datetime import datetime

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False


class SheetsService:
    """Service for Google Sheets integration"""
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    def __init__(self):
        if not SHEETS_AVAILABLE:
            raise ImportError("google-api-python-client and google-auth are required. Install with: pip install google-api-python-client google-auth")
        
        creds_path = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_PATH')
        self.sheet_id = os.environ.get('GOOGLE_SHEET_ID')
        
        if not creds_path or not self.sheet_id:
            raise ValueError("GOOGLE_SHEETS_CREDENTIALS_PATH and GOOGLE_SHEET_ID environment variables are required")
        
        if not os.path.exists(creds_path):
            raise FileNotFoundError(f"Credentials file not found: {creds_path}")
        
        credentials = Credentials.from_service_account_file(creds_path, scopes=self.SCOPES)
        self.service = build('sheets', 'v4', credentials=credentials)
        self.sheets = self.service.spreadsheets()
    
    def get_students_list(self, sheet_name: str = 'Students') -> List[Dict]:
        """
        Get list of students from the sheet.
        Expected columns: Roll Number, Name, Email, Year
        """
        try:
            result = self.sheets.values().get(
                spreadsheetId=self.sheet_id,
                range=f'{sheet_name}!A:D'
            ).execute()
            
            values = result.get('values', [])
            if not values:
                return []
            
            headers = values[0]
            students = []
            
            for row in values[1:]:
                if len(row) >= 3:
                    student = {
                        'roll_number': row[0] if len(row) > 0 else '',
                        'name': row[1] if len(row) > 1 else '',
                        'email': row[2] if len(row) > 2 else '',
                        'year': row[3] if len(row) > 3 else ''
                    }
                    students.append(student)
            
            return students
        except Exception as e:
            print(f"Error reading students from sheet: {e}")
            return []
    
    def update_viva_marks(
        self,
        lab_name: str,
        experiment_no: int,
        marks_data: List[Dict],
        sheet_name: str = None
    ) -> bool:
        """
        Update viva marks in a sheet.
        Creates a new sheet for the lab if it doesn't exist.
        
        Args:
            lab_name: Name of the lab
            experiment_no: Experiment number (1-10)
            marks_data: List of {'roll_number': str, 'name': str, 'marks': int, 'status': str}
            sheet_name: Optional custom sheet name
        """
        if not sheet_name:
            sheet_name = f"{lab_name}_Marks"
        
        try:
            # Get existing sheet data
            try:
                result = self.sheets.values().get(
                    spreadsheetId=self.sheet_id,
                    range=f'{sheet_name}!A:L'
                ).execute()
                existing_values = result.get('values', [])
            except:
                # Sheet doesn't exist, create headers
                existing_values = []
            
            # Build header row if needed
            if not existing_values:
                headers = ['Roll Number', 'Name']
                for i in range(1, 11):
                    headers.append(f'Exp {i}')
                existing_values = [headers]
            
            # Find or create rows for each student
            roll_to_row = {}
            for idx, row in enumerate(existing_values[1:], start=2):
                if row:
                    roll_to_row[row[0]] = idx
            
            updates = []
            
            for data in marks_data:
                roll = data['roll_number']
                marks = data.get('marks', 0)
                status = data.get('status', '')
                
                # Column for this experiment (0=Roll, 1=Name, 2=Exp1, ..., 11=Exp10)
                col_index = 1 + experiment_no  # 0-indexed
                col_letter = chr(ord('A') + col_index)
                
                if roll in roll_to_row:
                    row_num = roll_to_row[roll]
                else:
                    # Add new row
                    row_num = len(existing_values) + 1
                    roll_to_row[roll] = row_num
                    existing_values.append([roll, data.get('name', '')])
                
                # Prepare cell value
                cell_value = str(marks) if status != 'violated' else '0 (V)'
                
                updates.append({
                    'range': f'{sheet_name}!{col_letter}{row_num}',
                    'values': [[cell_value]]
                })
            
            # Batch update
            if updates:
                body = {'valueInputOption': 'RAW', 'data': updates}
                self.sheets.values().batchUpdate(
                    spreadsheetId=self.sheet_id,
                    body=body
                ).execute()
            
            return True
            
        except Exception as e:
            print(f"Error updating marks in sheet: {e}")
            return False
    
    def export_all_marks(self, lab_id: int) -> bool:
        """Export all marks for a lab to Google Sheets"""
        from models.user import LabConfig, VivaSession, Experiment, User
        from app import db
        
        try:
            lab = LabConfig.query.get(lab_id)
            if not lab:
                return False
            
            sheet_name = f"{lab.lab_name}_Marks"
            
            # Get all experiments and sessions
            for exp in lab.experiments:
                sessions = (
                    VivaSession.query
                    .filter_by(experiment_id=exp.id)
                    .filter(VivaSession.status.in_(['completed', 'violated']))
                    .all()
                )
                
                marks_data = []
                for session in sessions:
                    student = User.query.get(session.student_id)
                    if student:
                        marks_data.append({
                            'roll_number': student.roll_number,
                            'name': student.name,
                            'marks': session.obtained_marks,
                            'status': session.status
                        })
                
                if marks_data:
                    self.update_viva_marks(lab.lab_name, exp.experiment_no, marks_data, sheet_name)
            
            return True
            
        except Exception as e:
            print(f"Error exporting marks: {e}")
            return False


# Singleton instance
_sheets_service = None

def get_sheets_service() -> Optional[SheetsService]:
    """Get or create Sheets service instance"""
    global _sheets_service
    if _sheets_service is None:
        try:
            _sheets_service = SheetsService()
        except (ValueError, ImportError, FileNotFoundError) as e:
            print(f"Google Sheets not configured: {e}")
            return None
    return _sheets_service
