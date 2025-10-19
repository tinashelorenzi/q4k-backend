#!/usr/bin/env python3
"""
Test script to verify Digital Samba API authentication.
"""
import os
import sys
import django

# Add the project directory to Python path
sys.path.append('/home/nash/Documents/CodeProjects/CNT/Q4K/q4k-backend')

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quest4knowledge.settings')
django.setup()

from gigs.digital_samba import DigitalSambaAPI

def test_digital_samba_auth():
    """Test Digital Samba API authentication."""
    try:
        print("Testing Digital Samba API authentication...")
        
        # Initialize API client
        api = DigitalSambaAPI()
        print(f"Team ID: {api.team_id}")
        print(f"API URL: {api.api_url}")
        
        # Test room creation
        print("\nCreating a test room...")
        response = api.create_room(privacy="public")
        
        print("✅ SUCCESS! Room created successfully:")
        print(f"Room ID: {response.get('id')}")
        print(f"Room URL: {response.get('room_url')}")
        print(f"Friendly URL: {response.get('friendly_url')}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    success = test_digital_samba_auth()
    sys.exit(0 if success else 1)
