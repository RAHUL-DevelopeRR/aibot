"""
Database Cleanup Script - Removes old DSA Lab experiments and prepares for Google Sheets sync.

Run this script to clear existing experiments from the database:
    python cleanup_db.py

After running, use the teacher dashboard to sync experiments from Google Sheets.
"""
from app import create_app, db
from models.user import Subject, LabConfig, Experiment, VivaSchedule, VivaSession, StudentAnswer


def cleanup_experiments():
    """Remove all existing experiments, labs, and subjects to prepare for fresh sync"""
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("DATABASE CLEANUP - Removing old experiments")
        print("=" * 60)
        
        # Count existing records
        subjects_count = Subject.query.count()
        labs_count = LabConfig.query.count()
        experiments_count = Experiment.query.count()
        schedules_count = VivaSchedule.query.count()
        sessions_count = VivaSession.query.count()
        
        print(f"\nFound:")
        print(f"  - {subjects_count} subjects")
        print(f"  - {labs_count} lab configs")
        print(f"  - {experiments_count} experiments")
        print(f"  - {schedules_count} viva schedules")
        print(f"  - {sessions_count} viva sessions")
        
        if experiments_count == 0 and labs_count == 0:
            print("\n✓ Database is already clean. No experiments to remove.")
            return
        
        # Confirm
        confirm = input("\n⚠️  This will DELETE all experiments, schedules, and related data.\nType 'YES' to confirm: ")
        if confirm != 'YES':
            print("Cancelled.")
            return
        
        try:
            # Delete in order (respect foreign keys)
            print("\nDeleting records...")
            
            # Delete student answers
            answers_deleted = StudentAnswer.query.delete()
            print(f"  ✓ Deleted {answers_deleted} student answers")
            
            # Delete viva sessions
            sessions_deleted = VivaSession.query.delete()
            print(f"  ✓ Deleted {sessions_deleted} viva sessions")
            
            # Delete viva schedules
            schedules_deleted = VivaSchedule.query.delete()
            print(f"  ✓ Deleted {schedules_deleted} viva schedules")
            
            # Delete experiments
            experiments_deleted = Experiment.query.delete()
            print(f"  ✓ Deleted {experiments_deleted} experiments")
            
            # Delete lab configs
            labs_deleted = LabConfig.query.delete()
            print(f"  ✓ Deleted {labs_deleted} lab configs")
            
            # Delete subjects
            subjects_deleted = Subject.query.delete()
            print(f"  ✓ Deleted {subjects_deleted} subjects")
            
            db.session.commit()
            
            print("\n" + "=" * 60)
            print("✅ DATABASE CLEANED SUCCESSFULLY!")
            print("=" * 60)
            print("\nNext steps:")
            print("1. Set up your Google Sheets with 'Labs' and 'Experiments' sheets")
            print("2. Set GOOGLE_TEACHER_SHEET_ID environment variable")
            print("3. Log in as teacher and click 'Sync from Sheets' button")
            print("   OR run: python -c \"from services.sync_service import sync_experiments_from_sheets; print(sync_experiments_from_sheets())\"")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error during cleanup: {e}")


def cleanup_and_sync():
    """Clean database and immediately sync from Google Sheets"""
    app = create_app()
    with app.app_context():
        from services.sync_service import sync_experiments_from_sheets
        
        print("=" * 60)
        print("CLEANUP AND SYNC FROM GOOGLE SHEETS")
        print("=" * 60)
        
        # Check if sheets is configured
        import os
        if not os.environ.get('GOOGLE_TEACHER_SHEET_ID'):
            print("\n❌ GOOGLE_TEACHER_SHEET_ID not set!")
            print("Please set this environment variable to your Google Sheet ID.")
            return
        
        # Delete existing data
        print("\n1. Cleaning existing data...")
        try:
            StudentAnswer.query.delete()
            VivaSession.query.delete()
            VivaSchedule.query.delete()
            Experiment.query.delete()
            LabConfig.query.delete()
            Subject.query.delete()
            db.session.commit()
            print("   ✓ Old data removed")
        except Exception as e:
            db.session.rollback()
            print(f"   ❌ Cleanup failed: {e}")
            return
        
        # Sync from Google Sheets
        print("\n2. Syncing from Google Sheets...")
        result = sync_experiments_from_sheets()
        
        if result['success']:
            print(f"   ✓ {result['message']}")
            if result['data']:
                print(f"\n   Labs synced: {', '.join(result['data'].get('labs', []))}")
                print(f"   Experiments: {len(result['data'].get('experiments', []))}")
        else:
            print(f"   ❌ {result['message']}")
        
        print("\n" + "=" * 60)
        print("DONE!")
        print("=" * 60)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--sync':
        cleanup_and_sync()
    else:
        cleanup_experiments()
        print("\nTip: Use 'python cleanup_db.py --sync' to also sync from Google Sheets immediately.")
