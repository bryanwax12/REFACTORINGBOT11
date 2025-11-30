#!/usr/bin/env python3
"""
Test bot_instance availability in app.state
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/frontend/.env')

# Get backend URL from environment
BACKEND_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://easyshipbot.preview.emergentagent.com')

def test_bot_instance_availability():
    """Test if bot_instance is available via a debug endpoint"""
    print("🔍 Testing bot_instance availability...")
    
    try:
        # Try to access a debug endpoint that shows bot status
        response = requests.get(f"{BACKEND_URL}/debug/bot-status", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Bot status response: {json.dumps(data, indent=2)}")
        else:
            print(f"⚠️ Debug endpoint not available: {response.status_code}")
        
        # Try to access the monitoring health endpoint
        response = requests.get(f"{BACKEND_URL}/monitoring/health", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check response: {json.dumps(data, indent=2)}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing bot instance: {e}")
        return False

if __name__ == "__main__":
    test_bot_instance_availability()