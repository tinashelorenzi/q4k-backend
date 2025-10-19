"""
Cloudflare Turnstile verification utility.
Validates Turnstile tokens to prevent bot access.
"""
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def verify_turnstile_token(token, ip_address=None):
    """
    Verify a Cloudflare Turnstile token.
    
    Args:
        token (str): The Turnstile token to verify
        ip_address (str, optional): The user's IP address
        
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if not token:
        return False, "Turnstile token is required"
    
    # Get secret key from settings
    secret_key = getattr(settings, 'TURNSTILE_SECRET_KEY', None)
    
    # Allow bypass in development if no secret key is configured
    if not secret_key or secret_key == 'your_turnstile_secret_key_here':
        if settings.DEBUG:
            logger.warning("Turnstile validation bypassed in DEBUG mode (no secret key configured)")
            return True, None
        else:
            logger.error("Turnstile secret key not configured in production")
            return False, "Turnstile verification not configured"
    
    # Prepare verification request
    verify_url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    payload = {
        'secret': secret_key,
        'response': token,
    }
    
    # Add IP address if provided (optional but recommended)
    if ip_address:
        payload['remoteip'] = ip_address
    
    try:
        # Send verification request to Cloudflare
        response = requests.post(verify_url, data=payload, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get('success'):
            logger.info(f"Turnstile verification successful for token: {token[:20]}...")
            return True, None
        else:
            error_codes = result.get('error-codes', [])
            logger.warning(f"Turnstile verification failed: {error_codes}")
            
            # Map error codes to user-friendly messages
            error_messages = {
                'missing-input-secret': 'Server configuration error',
                'invalid-input-secret': 'Server configuration error',
                'missing-input-response': 'Verification token missing',
                'invalid-input-response': 'Invalid verification token',
                'bad-request': 'Invalid verification request',
                'timeout-or-duplicate': 'Verification expired or already used',
            }
            
            # Get first error message or use generic message
            first_error = error_codes[0] if error_codes else 'unknown'
            error_message = error_messages.get(first_error, 'Verification failed')
            
            return False, error_message
            
    except requests.exceptions.Timeout:
        logger.error("Turnstile verification timeout")
        return False, "Verification service timeout"
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Turnstile verification request failed: {e}")
        return False, "Verification service error"
    
    except Exception as e:
        logger.error(f"Unexpected error during Turnstile verification: {e}")
        return False, "Verification failed"


def get_client_ip(request):
    """
    Extract client IP address from request.
    
    Args:
        request: Django request object
        
    Returns:
        str: Client IP address
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

