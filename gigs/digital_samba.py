"""
Digital Samba API integration for creating and managing video conference rooms.
"""
import requests
import base64
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class DigitalSambaAPI:
    """Digital Samba API client for room management."""
    
    def __init__(self):
        self.team_id = settings.DIGITAL_SAMBA_TEAM_ID
        self.developer_key = settings.DIGITAL_SAMBA_DEVELOPER_KEY
        self.api_url = settings.DIGITAL_SAMBA_API_URL
        
        if not self.team_id or not self.developer_key:
            raise ImproperlyConfigured(
                "Digital Samba credentials not configured. Please set "
                "DIGITAL_SAMBA_TEAM_ID and DIGITAL_SAMBA_DEVELOPER_KEY in your environment."
            )
    
    def _get_auth_header(self):
        """Get Basic Auth header for API requests."""
        credentials = f"{self.team_id}:{self.developer_key}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded_credentials}"
    
    def _get_auth_tuple(self):
        """Get auth tuple for requests (alternative to Basic Auth header)."""
        return (self.team_id, self.developer_key)
    
    def create_room(self, friendly_url=None, privacy="public", room_settings=None):
        """
        Create a new Digital Samba room.
        
        Args:
            friendly_url (str): Optional friendly URL for the room (if not provided, auto-generated)
            privacy (str): Room privacy setting ('public' or 'private')
            room_settings (dict): Optional room configuration settings
            
        Returns:
            dict: Room creation response from Digital Samba API
        """
        url = f"{self.api_url}/rooms"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        data = {
            "privacy": privacy
        }
        
        # Add friendly_url if provided
        if friendly_url:
            data["friendly_url"] = friendly_url
        
        # Add room settings if provided
        if room_settings:
            data.update(room_settings)
        
        try:
            # Use auth tuple instead of Authorization header (matches curl --user format)
            response = requests.post(url, headers=headers, json=data, auth=self._get_auth_tuple(), timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to create Digital Samba room: {str(e)}")
    
    def get_room(self, room_id):
        """
        Get room information by room ID.
        
        Args:
            room_id (str): Digital Samba room ID
            
        Returns:
            dict: Room information from Digital Samba API
        """
        url = f"{self.api_url}/rooms/{room_id}"
        
        headers = {}
        
        try:
            response = requests.get(url, headers=headers, auth=self._get_auth_tuple(), timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to get Digital Samba room: {str(e)}")
    
    def delete_room(self, room_id):
        """
        Delete a Digital Samba room.
        
        Args:
            room_id (str): Digital Samba room ID
            
        Returns:
            bool: True if successful
        """
        url = f"{self.api_url}/rooms/{room_id}"
        
        headers = {}
        
        try:
            response = requests.delete(url, headers=headers, auth=self._get_auth_tuple(), timeout=30)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to delete Digital Samba room: {str(e)}")
    
    def generate_room_url(self, friendly_url):
        """
        Generate the full room URL for Digital Samba.
        
        Args:
            friendly_url (str): Room friendly URL
            
        Returns:
            str: Full Digital Samba room URL
        """
        # Extract team name from team_id (assuming format like "team-name-123")
        team_name = self.team_id.split('-')[0] if '-' in self.team_id else self.team_id
        return f"https://{team_name}.digitalsamba.com/{friendly_url}"
