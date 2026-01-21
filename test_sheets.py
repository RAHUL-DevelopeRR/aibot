"""
Test script for Google Sheets integration.
Run this to verify connection to both sheets.
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_sheets_connection():
    """Test connection to both Google Sheets"""
    print("=" * 60)
    print("Testing Google Sheets Integration")
    print("=" * 60)
    
    # Check environment variables
    creds_path = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_PATH')
    student_sheet_id = os.environ.get('GOOGLE_SHEET_ID')
    teacher_sheet_id = os.environ.get('GOOGLE_TEACHER_SHEET_ID')
    
    print(f"\n1. Environment Variables:")
    print(f"   Credentials Path: {creds_path}")
    print(f"   Student Sheet ID: {student_sheet_id[:20]}..." if student_sheet_id else "   Student Sheet ID: NOT SET")
    print(f"   Teacher Sheet ID: {teacher_sheet_id[:20]}..." if teacher_sheet_id else "   Teacher Sheet ID: NOT SET")
    
    if not creds_path or not os.path.exists(creds_path):
        print(f"\n❌ ERROR: Credentials file not found at '{creds_path}'")
        return False
    
    print(f"\n2. Initializing Sheets Service...")
    
    try:
        from services.sheets_service import get_sheets_service
        sheets = get_sheets_service()
        
        if not sheets:
            print("❌ ERROR: Could not initialize Sheets Service")
            return False
        
        print("   ✓ Sheets Service initialized successfully")
        
        # Test Teacher Sheet - Get experiments
        print(f"\n3. Testing Teacher Sheet (Experiments List)...")
        try:
            experiments = sheets.get_experiments_list()
            print(f"   ✓ Found {len(experiments)} experiments")
            if experiments:
                for exp in experiments[:3]:  # Show first 3
                    print(f"      - {exp.get('experiment_no', 'N/A')}: {exp.get('experiment_name', 'N/A')}")
                if len(experiments) > 3:
                    print(f"      ... and {len(experiments) - 3} more")
        except Exception as e:
            print(f"   ⚠ Could not read experiments: {e}")
        
        # Test Teacher Sheet - Get teacher details
        print(f"\n4. Testing Teacher Sheet (Teacher Details)...")
        try:
            teachers = sheets.get_teacher_details()
            print(f"   ✓ Found {len(teachers)} teachers")
            if teachers:
                for teacher in teachers[:3]:  # Show first 3
                    print(f"      - {teacher.get('name', 'N/A')} ({teacher.get('email', 'N/A')})")
                if len(teachers) > 3:
                    print(f"      ... and {len(teachers) - 3} more")
        except Exception as e:
            print(f"   ⚠ Could not read teachers: {e}")
        
        # Test Teacher Sheet - Get labs
        print(f"\n5. Testing Teacher Sheet (Lab Info)...")
        try:
            labs = sheets.get_lab_info()
            print(f"   ✓ Found {len(labs)} labs")
            if labs:
                for lab in labs[:3]:  # Show first 3
                    print(f"      - {lab.get('lab_name', 'N/A')} ({lab.get('subject', 'N/A')})")
                if len(labs) > 3:
                    print(f"      ... and {len(labs) - 3} more")
        except Exception as e:
            print(f"   ⚠ Could not read labs: {e}")
        
        # Test Student Sheet - Get marks
        print(f"\n6. Testing Student Sheet (Viva Marks)...")
        try:
            marks = sheets.get_student_marks()
            print(f"   ✓ Found {len(marks)} student records")
            if marks:
                for student in marks[:3]:  # Show first 3
                    print(f"      - {student.get('roll_number', 'N/A')}: {student.get('name', 'N/A')}")
                if len(marks) > 3:
                    print(f"      ... and {len(marks) - 3} more")
        except Exception as e:
            print(f"   ⚠ Could not read student marks: {e}")
        
        print("\n" + "=" * 60)
        print("✓ Google Sheets Integration Test Complete!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_enter_marks():
    """Test entering marks for a student"""
    print("\n" + "=" * 60)
    print("Testing Enter Viva Marks")
    print("=" * 60)
    
    try:
        from services.sheets_service import get_sheets_service
        sheets = get_sheets_service()
        
        if not sheets:
            print("❌ ERROR: Could not initialize Sheets Service")
            return False
        
        # Example: Enter marks for a test student
        test_roll = "TEST001"
        test_name = "Test Student"
        test_marks = {
            1: 8,   # Experiment 1
            2: 9,   # Experiment 2
            3: 7,   # Experiment 3
        }
        
        print(f"\nEntering marks for {test_name} ({test_roll}):")
        for exp, marks in test_marks.items():
            print(f"   Experiment {exp}: {marks} marks")
        
        success = sheets.enter_student_viva_marks(
            roll_number=test_roll,
            student_name=test_name,
            experiment_marks=test_marks
        )
        
        if success:
            print("\n✓ Marks entered successfully!")
        else:
            print("\n❌ Failed to enter marks")
        
        return success
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    # Run connection test
    test_sheets_connection()
    
    # Uncomment below to test entering marks
    # test_enter_marks()
