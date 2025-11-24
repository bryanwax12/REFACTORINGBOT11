"""
Utility to clear old conversation states from PicklePersistence
Run this script if users experience "stuck" conversations
"""
import pickle
import sys
from pathlib import Path

def clear_persistence_file():
    """Clear all conversation states from persistence file"""
    persistence_file = Path(__file__).parent.parent / 'data' / 'conversation_state.pkl'
    
    if not persistence_file.exists():
        print(f"❌ Persistence file not found: {persistence_file}")
        return False
    
    print(f"📂 Found persistence file: {persistence_file}")
    print(f"📏 Current size: {persistence_file.stat().st_size / 1024:.1f} KB")
    
    # Backup current file
    backup_file = persistence_file.with_suffix('.pkl.backup')
    import shutil
    shutil.copy(persistence_file, backup_file)
    print(f"💾 Backup created: {backup_file}")
    
    try:
        # Load current data
        with open(persistence_file, 'rb') as f:
            data = pickle.load(f)
        
        print(f"\n📊 Current data structure:")
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    print(f"   {key}: {len(value)} entries")
                else:
                    print(f"   {key}: {type(value).__name__}")
        
        # Clear conversations but keep other data
        if 'conversations' in data and isinstance(data['conversations'], dict):
            old_count = len(data['conversations'])
            data['conversations'].clear()
            print(f"\n🧹 Cleared {old_count} conversation states")
        
        # Clear user_data for all users (removes stuck states)
        if 'user_data' in data and isinstance(data['user_data'], dict):
            old_count = len(data['user_data'])
            # Keep db_user but clear conversation-related data
            for user_id in list(data['user_data'].keys()):
                if isinstance(data['user_data'][user_id], dict):
                    # Keep only essential keys
                    db_user = data['user_data'][user_id].get('db_user')
                    data['user_data'][user_id] = {}
                    if db_user:
                        data['user_data'][user_id]['db_user'] = db_user
            print(f"🧹 Cleaned {old_count} user_data entries")
        
        # Save cleaned data
        with open(persistence_file, 'wb') as f:
            pickle.dump(data, f)
        
        new_size = persistence_file.stat().st_size
        print(f"\n✅ Persistence file cleaned!")
        print(f"📏 New size: {new_size / 1024:.1f} KB")
        print(f"💾 Old file backed up to: {backup_file}")
        print(f"\n⚠️  Restart backend to apply changes: sudo supervisorctl restart backend")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print(f"💾 Restoring from backup...")
        shutil.copy(backup_file, persistence_file)
        return False


if __name__ == '__main__':
    print("=" * 60)
    print("🧹 CONVERSATION STATE CLEANER")
    print("=" * 60)
    print("\nThis script will:")
    print("  1. Clear all active conversation states")
    print("  2. Clean user_data (keep only db_user)")
    print("  3. Create a backup before making changes")
    print("\n⚠️  This will NOT affect user accounts or order data!")
    print("=" * 60)
    
    if len(sys.argv) > 1 and sys.argv[1] == '--force':
        confirm = 'y'
    else:
        confirm = input("\n👉 Proceed with cleaning? (y/n): ").lower().strip()
    
    if confirm == 'y':
        success = clear_persistence_file()
        sys.exit(0 if success else 1)
    else:
        print("❌ Cancelled")
        sys.exit(1)
