#!/usr/bin/env python3
"""
Environment loader for deployment
Ensures MONGO_URL is properly loaded from environment or .env file
"""
import os
import sys
from pathlib import Path

def load_environment():
    """Load environment variables with fallback to .env file"""
    
    # Check if MONGO_URL is already set (deployment environment)
    mongo_url = os.environ.get('MONGO_URL')
    
    if mongo_url:
        print(f"✅ MONGO_URL loaded from environment")
        return True
    
    # Fallback to .env file
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        print(f"📄 Loading from .env file: {env_file}")
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    if key and not os.environ.get(key):
                        os.environ[key] = value
        
        # Verify MONGO_URL was loaded
        if os.environ.get('MONGO_URL'):
            print(f"✅ MONGO_URL loaded from .env file")
            return True
        else:
            print(f"⚠️ MONGO_URL not found in .env file")
            return False
    else:
        print(f"⚠️ .env file not found: {env_file}")
        return False

if __name__ == '__main__':
    success = load_environment()
    sys.exit(0 if success else 1)
