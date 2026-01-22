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
    """Service for Google Sheets integration
    
    Supports two sheets:
    - Student Sheet (GOOGLE_SHEET_ID): For entering Viva marks for 10 Experiments
    - Teacher Sheet (GOOGLE_TEACHER_SHEET_ID): For retrieving Teacher details and List of Experiments
    """
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    def __init__(self):
        if not SHEETS_AVAILABLE:
            raise ImportError("google-api-python-client and google-auth are required. Install with: pip install google-api-python-client google-auth")
        
        creds_path = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_PATH')
        # Student Sheet for entering Viva marks
        self.student_sheet_id = os.environ.get('GOOGLE_SHEET_ID')
        # Teacher Sheet for retrieving teacher details and experiments
        self.teacher_sheet_id = os.environ.get('GOOGLE_TEACHER_SHEET_ID')
        
        # Keep legacy reference for backward compatibility
        self.sheet_id = self.student_sheet_id
        
        if not creds_path or not self.student_sheet_id:
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
    
    # ==============================================
    # TEACHER SHEET METHODS
    # ==============================================
    
    def get_teacher_details(self, sheet_name: str = 'Teachers') -> List[Dict]:
        """
        Get list of teachers from the Teacher Sheet.
        Expected columns: Teacher ID, Name, Email, Department, Designation, Subjects
        
        Returns:
            List of teacher dictionaries
        """
        if not self.teacher_sheet_id:
            print("Teacher Sheet ID not configured")
            return []
        
        try:
            result = self.sheets.values().get(
                spreadsheetId=self.teacher_sheet_id,
                range=f'{sheet_name}!A:F'
            ).execute()
            
            values = result.get('values', [])
            if not values:
                return []
            
            headers = values[0]
            teachers = []
            
            for row in values[1:]:
                if row:
                    teacher = {
                        'teacher_id': row[0] if len(row) > 0 else '',
                        'name': row[1] if len(row) > 1 else '',
                        'email': row[2] if len(row) > 2 else '',
                        'department': row[3] if len(row) > 3 else '',
                        'designation': row[4] if len(row) > 4 else '',
                        'subjects': row[5] if len(row) > 5 else ''
                    }
                    teachers.append(teacher)
            
            return teachers
        except Exception as e:
            print(f"Error reading teachers from sheet: {e}")
            return []
    
    def get_experiments_list(self, sheet_name: str = 'Experiments') -> List[Dict]:
        """
        Get list of experiments from the Teacher Sheet.
        Expected columns: Exp No, Experiment Name, Lab Name, Description, Max Marks
        
        Returns:
            List of experiment dictionaries
        """
        if not self.teacher_sheet_id:
            print("Teacher Sheet ID not configured")
            return []
        
        try:
            result = self.sheets.values().get(
                spreadsheetId=self.teacher_sheet_id,
                range=f'{sheet_name}!A:E'
            ).execute()
            
            values = result.get('values', [])
            if not values:
                return []
            
            headers = values[0]
            experiments = []
            
            for row in values[1:]:
                if row:
                    experiment = {
                        'experiment_no': row[0] if len(row) > 0 else '',
                        'experiment_name': row[1] if len(row) > 1 else '',
                        'lab_name': row[2] if len(row) > 2 else '',
                        'description': row[3] if len(row) > 3 else '',
                        'max_marks': row[4] if len(row) > 4 else '10'
                    }
                    experiments.append(experiment)
            
            return experiments
        except Exception as e:
            print(f"Error reading experiments from sheet: {e}")
            return []
    
    def get_lab_info(self, sheet_name: str = 'Labs') -> List[Dict]:
        """
        Get lab configuration from the Teacher Sheet.
        Expected columns: Lab ID, Lab Name, Subject, Year, Total Experiments
        
        Returns:
            List of lab configuration dictionaries
        """
        if not self.teacher_sheet_id:
            print("Teacher Sheet ID not configured")
            return []
        
        try:
            result = self.sheets.values().get(
                spreadsheetId=self.teacher_sheet_id,
                range=f'{sheet_name}!A:E'
            ).execute()
            
            values = result.get('values', [])
            if not values:
                return []
            
            headers = values[0]
            labs = []
            
            for row in values[1:]:
                if row:
                    lab = {
                        'lab_id': row[0] if len(row) > 0 else '',
                        'lab_name': row[1] if len(row) > 1 else '',
                        'subject': row[2] if len(row) > 2 else '',
                        'year': row[3] if len(row) > 3 else '',
                        'total_experiments': row[4] if len(row) > 4 else '10'
                    }
                    labs.append(lab)
            
            return labs
        except Exception as e:
            print(f"Error reading labs from sheet: {e}")
            return []
    
    # ==============================================
    # STUDENT SHEET METHODS - Viva Marks Entry
    # ==============================================
    
    def enter_student_viva_marks(
        self,
        roll_number: str,
        student_name: str,
        experiment_marks: Dict[int, int],
        sheet_name: str = 'Sheet1'
    ) -> bool:
        """
        Enter viva marks for a student for multiple experiments (1-10).
        Uses the Student Sheet (GOOGLE_SHEET_ID).
        
        Args:
            roll_number: Student roll number
            student_name: Student name
            experiment_marks: Dict mapping experiment number (1-10) to marks
            sheet_name: Sheet name in the Student Sheet
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get existing data
            try:
                result = self.sheets.values().get(
                    spreadsheetId=self.student_sheet_id,
                    range=f'{sheet_name}!A:L'
                ).execute()
                existing_values = result.get('values', [])
            except:
                existing_values = []
            
            # Build header if needed
            if not existing_values:
                headers = ['Roll Number', 'Name']
                for i in range(1, 11):
                    headers.append(f'Exp {i}')
                existing_values = [headers]
                # Write headers first
                self.sheets.values().update(
                    spreadsheetId=self.student_sheet_id,
                    range=f'{sheet_name}!A1:L1',
                    valueInputOption='RAW',
                    body={'values': [headers]}
                ).execute()
            
            # Find student row
            student_row = None
            for idx, row in enumerate(existing_values[1:], start=2):
                if row and row[0] == roll_number:
                    student_row = idx
                    break
            
            updates = []
            
            if student_row is None:
                # Add new student row
                student_row = len(existing_values) + 1
                # Add roll number and name
                updates.append({
                    'range': f'{sheet_name}!A{student_row}:B{student_row}',
                    'values': [[roll_number, student_name]]
                })
            
            # Update experiment marks
            for exp_no, marks in experiment_marks.items():
                if 1 <= exp_no <= 10:
                    col_index = 1 + exp_no  # A=0, B=1, C=2 (Exp1), ..., L=11 (Exp10)
                    col_letter = chr(ord('A') + col_index)
                    updates.append({
                        'range': f'{sheet_name}!{col_letter}{student_row}',
                        'values': [[str(marks)]]
                    })
            
            # Batch update
            if updates:
                body = {'valueInputOption': 'RAW', 'data': updates}
                self.sheets.values().batchUpdate(
                    spreadsheetId=self.student_sheet_id,
                    body=body
                ).execute()
            
            return True
            
        except Exception as e:
            print(f"Error entering student viva marks: {e}")
            return False
    
    def get_student_marks(self, roll_number: str = None, sheet_name: str = 'Sheet1') -> List[Dict]:
        """
        Get student marks from the Student Sheet.
        
        Args:
            roll_number: Optional specific roll number to filter by
            sheet_name: Sheet name in the Student Sheet
            
        Returns:
            List of student marks dictionaries
        """
        try:
            result = self.sheets.values().get(
                spreadsheetId=self.student_sheet_id,
                range=f'{sheet_name}!A:L'
            ).execute()
            
            values = result.get('values', [])
            if not values or len(values) < 2:
                return []
            
            students_marks = []
            
            for row in values[1:]:
                if row:
                    student_roll = row[0] if len(row) > 0 else ''
                    
                    # Filter by roll number if specified
                    if roll_number and student_roll != roll_number:
                        continue
                    
                    student_data = {
                        'roll_number': student_roll,
                        'name': row[1] if len(row) > 1 else '',
                        'experiments': {}
                    }
                    
                    # Extract experiment marks (columns C to L = Exp 1 to 10)
                    for exp_no in range(1, 11):
                        col_index = 1 + exp_no
                        if len(row) > col_index:
                            try:
                                marks = int(row[col_index]) if row[col_index] else None
                            except ValueError:
                                marks = row[col_index]  # Keep as string if not a number
                            student_data['experiments'][exp_no] = marks
                        else:
                            student_data['experiments'][exp_no] = None
                    
                    students_marks.append(student_data)
            
            return students_marks
            
        except Exception as e:
            print(f"Error reading student marks: {e}")
            return []


    # ==============================================
    # STUDENT VALIDATION & MARKS - Google Sheets as Source of Truth
    # ==============================================
    
    def validate_student_reg_no(self, reg_no: str, sheet_name: str = 'Sheet1') -> Optional[Dict]:
        """
        Validate if a student Reg_No exists in the Google Sheets.
        Case-insensitive comparison.
        
        Args:
            reg_no: Student registration number (12 digit, e.g., 927623BCB041)
            sheet_name: Sheet name in the Student Sheet
            
        Returns:
            Student dict if found, None otherwise
        """
        try:
            result = self.sheets.values().get(
                spreadsheetId=self.student_sheet_id,
                range=f'{sheet_name}!A:B'
            ).execute()
            
            values = result.get('values', [])
            if not values or len(values) < 2:
                return None
            
            # Normalize input reg_no for case-insensitive comparison
            reg_no_upper = reg_no.strip().upper()
            
            for row in values[1:]:  # Skip header
                if row:
                    sheet_reg_no = (row[0] if len(row) > 0 else '').strip().upper()
                    if sheet_reg_no == reg_no_upper:
                        return {
                            'reg_no': row[0] if len(row) > 0 else '',
                            'name': row[1] if len(row) > 1 else ''
                        }
            
            return None
            
        except Exception as e:
            print(f"Error validating student reg_no: {e}")
            return None
    
    def get_all_students_with_marks(self, sheet_name: str = 'Sheet1') -> List[Dict]:
        """
        Get all students with their experiment marks from Google Sheets.
        This is the ONLY source of truth for student data.
        
        Expected columns: Reg_No, Name, Exp_1 (Marks), ..., Exp_10 (Marks)
        
        Returns:
            List of student dictionaries with marks
        """
        try:
            result = self.sheets.values().get(
                spreadsheetId=self.student_sheet_id,
                range=f'{sheet_name}!A:L'
            ).execute()
            
            values = result.get('values', [])
            if not values or len(values) < 1:
                return []
            
            students = []
            
            for row in values[1:]:  # Skip header
                if row and len(row) > 0 and row[0]:  # Must have Reg_No
                    student = {
                        'reg_no': row[0] if len(row) > 0 else '',
                        'name': row[1] if len(row) > 1 else '',
                        'experiments': {}
                    }
                    
                    # Extract experiment marks (columns C to L = Exp 1 to 10)
                    for exp_no in range(1, 11):
                        col_index = 1 + exp_no  # C=2 (Exp1), D=3 (Exp2), ...
                        if len(row) > col_index and row[col_index]:
                            try:
                                student['experiments'][exp_no] = int(row[col_index])
                            except ValueError:
                                student['experiments'][exp_no] = row[col_index]
                        else:
                            student['experiments'][exp_no] = None
                    
                    students.append(student)
            
            return students
            
        except Exception as e:
            print(f"Error getting students with marks: {e}")
            return []
    
    def update_student_experiment_mark(
        self, 
        reg_no: str, 
        experiment_no: int, 
        marks: int, 
        sheet_name: str = 'Sheet1'
    ) -> bool:
        """
        Update a specific experiment mark for a student by Reg_No.
        Only updates the specific cell, does not modify other data.
        
        Args:
            reg_no: Student registration number
            experiment_no: Experiment number (1-10)
            marks: Marks to update
            sheet_name: Sheet name
            
        Returns:
            True if successful, False otherwise
        """
        if experiment_no < 1 or experiment_no > 10:
            print(f"Invalid experiment number: {experiment_no}")
            return False
        
        try:
            # First, find the row for this Reg_No
            result = self.sheets.values().get(
                spreadsheetId=self.student_sheet_id,
                range=f'{sheet_name}!A:A'
            ).execute()
            
            values = result.get('values', [])
            if not values:
                print("No data in sheet")
                return False
            
            # Find row by Reg_No (case-insensitive)
            reg_no_upper = reg_no.strip().upper()
            target_row = None
            
            for idx, row in enumerate(values):
                if row:
                    sheet_reg_no = row[0].strip().upper() if row[0] else ''
                    if sheet_reg_no == reg_no_upper:
                        target_row = idx + 1  # 1-indexed for Sheets API
                        break
            
            if target_row is None:
                print(f"Student with Reg_No {reg_no} not found")
                return False
            
            # Calculate column letter for experiment (C=Exp1, D=Exp2, ..., L=Exp10)
            col_letter = chr(ord('C') + experiment_no - 1)  # C for Exp1, D for Exp2, etc.
            
            # Update only the specific cell
            cell_range = f'{sheet_name}!{col_letter}{target_row}'
            
            self.sheets.values().update(
                spreadsheetId=self.student_sheet_id,
                range=cell_range,
                valueInputOption='RAW',
                body={'values': [[str(marks)]]}
            ).execute()
            
            print(f"Updated {reg_no} Exp_{experiment_no} = {marks} at {cell_range}")
            return True
            
        except Exception as e:
            print(f"Error updating student experiment mark: {e}")
            return False
    
    def get_student_by_reg_no(self, reg_no: str, sheet_name: str = 'Sheet1') -> Optional[Dict]:
        """
        Get a single student's data by Reg_No from Google Sheets.
        
        Args:
            reg_no: Student registration number
            sheet_name: Sheet name
            
        Returns:
            Student dict with marks if found, None otherwise
        """
        try:
            result = self.sheets.values().get(
                spreadsheetId=self.student_sheet_id,
                range=f'{sheet_name}!A:L'
            ).execute()
            
            values = result.get('values', [])
            if not values or len(values) < 2:
                return None
            
            reg_no_upper = reg_no.strip().upper()
            
            for row in values[1:]:  # Skip header
                if row:
                    sheet_reg_no = (row[0] if len(row) > 0 else '').strip().upper()
                    if sheet_reg_no == reg_no_upper:
                        student = {
                            'reg_no': row[0] if len(row) > 0 else '',
                            'name': row[1] if len(row) > 1 else '',
                            'experiments': {}
                        }
                        
                        for exp_no in range(1, 11):
                            col_index = 1 + exp_no
                            if len(row) > col_index and row[col_index]:
                                try:
                                    student['experiments'][exp_no] = int(row[col_index])
                                except ValueError:
                                    student['experiments'][exp_no] = row[col_index]
                            else:
                                student['experiments'][exp_no] = None
                        
                        return student
            
            return None
            
        except Exception as e:
            print(f"Error getting student by reg_no: {e}")
            return None


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
