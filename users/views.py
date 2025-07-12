from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.conf import settings
import logging

from .models import User, TutorProfile
from .serializers import (
    LoginSerializer,
    LoginResponseSerializer,
    UserSerializer,
    TutorProfileSerializer,
    LogoutSerializer,
    TokenRefreshResponseSerializer,
    UserSettingsSerializer
)

# Set up logging
logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Extract client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_tokens_for_user(user):
    """Generate JWT tokens for a user."""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    API endpoint for user login with email and password.
    
    Returns JWT tokens and user information upon successful authentication.
    """
    try:
        serializer = LoginSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            # Record successful login
            ip_address = get_client_ip(request)
            user.record_successful_login(ip_address)
            
            # Update last login
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])
            
            # Generate tokens
            tokens = get_tokens_for_user(user)
            
            # Prepare response data
            response_data = {
                'access_token': tokens['access'],
                'refresh_token': tokens['refresh'],
                'user': UserSerializer(user).data,
                'message': 'Login successful'
            }
            
            # Add tutor information if user is a tutor
            if user.is_tutor:
                try:
                    tutor_profile = user.tutor_profile
                    response_data['tutor_profile'] = TutorProfileSerializer(tutor_profile).data
                    
                    # Add tutor record information if linked
                    if tutor_profile.tutor:
                        from tutors.serializers import TutorSerializer
                        response_data['tutor'] = TutorSerializer(tutor_profile.tutor).data
                    else:
                        response_data['tutor'] = None
                        
                except TutorProfile.DoesNotExist:
                    response_data['tutor_profile'] = None
                    response_data['tutor'] = None
            
            # Log successful login
            logger.info(f"Successful login for user {user.email} from IP {ip_address}")
            
            return Response(response_data, status=status.HTTP_200_OK)
        
        # Return validation errors
        return Response({
            'error': 'Login failed',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred during login.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    API endpoint for user logout.
    
    Blacklists the provided refresh token.
    """
    try:
        serializer = LogoutSerializer(data=request.data)
        
        if serializer.is_valid():
            refresh_token = serializer.validated_data['refresh_token']
            
            try:
                # Blacklist the refresh token
                token = RefreshToken(refresh_token)
                token.blacklist()
                
                # Log successful logout
                logger.info(f"User {request.user.email} logged out successfully")
                
                return Response({
                    'message': 'Logout successful'
                }, status=status.HTTP_200_OK)
                
            except TokenError as e:
                return Response({
                    'error': 'Invalid or expired refresh token',
                    'details': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'error': 'Logout failed',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred during logout.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def token_refresh_view(request):
    """
    API endpoint to refresh access token using refresh token.
    """
    try:
        refresh_token = request.data.get('refresh_token')
        
        if not refresh_token:
            return Response({
                'error': 'Refresh token is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            refresh = RefreshToken(refresh_token)
            new_access_token = str(refresh.access_token)
            
            return Response({
                'access_token': new_access_token,
                'message': 'Token refreshed successfully'
            }, status=status.HTTP_200_OK)
            
        except TokenError as e:
            return Response({
                'error': 'Invalid or expired refresh token',
                'details': str(e)
            }, status=status.HTTP_401_UNAUTHORIZED)
    
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred during token refresh.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile_view(request):
    """
    API endpoint to get current user's profile information.
    """
    try:
        user = request.user
        response_data = {
            'user': UserSerializer(user).data
        }
        
        # Add tutor information if user is a tutor
        if user.is_tutor:
            try:
                tutor_profile = user.tutor_profile
                response_data['tutor_profile'] = TutorProfileSerializer(tutor_profile).data
                
                # Add tutor record information if linked
                if tutor_profile.tutor:
                    from tutors.serializers import TutorSerializer
                    response_data['tutor'] = TutorSerializer(tutor_profile.tutor).data
                else:
                    response_data['tutor'] = None
                    
            except TutorProfile.DoesNotExist:
                response_data['tutor_profile'] = None
                response_data['tutor'] = None
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"User profile error: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred while fetching profile.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_auth_view(request):
    """
    API endpoint to check if user is authenticated and get basic info.
    """
    try:
        user = request.user
        
        return Response({
            'authenticated': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.get_full_name(),
                'user_type': user.user_type,
                'is_verified': user.is_verified,
                'is_approved': user.is_approved,
            },
            'message': 'User is authenticated'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Auth check error: {str(e)}")
        return Response({
            'authenticated': False,
            'error': 'Authentication check failed.'
        }, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_user_profile(request):
    """
    Update current user's profile information (name, email, phone, etc.)
    """
    try:
        user = request.user
        partial = request.method == 'PATCH'
        
        # Use UserSerializer with partial update
        serializer = UserSerializer(user, data=request.data, partial=partial)
        
        if serializer.is_valid():
            # Check if email is being changed and if it's unique
            if 'email' in request.data:
                new_email = request.data['email']
                if new_email != user.email and User.objects.filter(email=new_email).exists():
                    return Response({
                        'error': 'Email already exists',
                        'detail': 'This email address is already in use.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            serializer.save()
            
            logger.info(f"User {user.email} updated their profile")
            
            return Response({
                'message': 'Profile updated successfully',
                'user': serializer.data
            }, status=status.HTTP_200_OK)
        
        return Response({
            'error': 'Validation failed',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Profile update error: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred while updating profile.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change current user's password
    """
    try:
        user = request.user
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')
        
        # Validate required fields
        if not all([current_password, new_password, confirm_password]):
            return Response({
                'error': 'Missing required fields',
                'detail': 'current_password, new_password, and confirm_password are required.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check current password
        if not user.check_password(current_password):
            return Response({
                'error': 'Invalid current password',
                'detail': 'The current password you entered is incorrect.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check password confirmation
        if new_password != confirm_password:
            return Response({
                'error': 'Password mismatch',
                'detail': 'New password and confirmation do not match.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate new password
        try:
            validate_password(new_password, user)
        except DjangoValidationError as e:
            return Response({
                'error': 'Password validation failed',
                'detail': list(e.messages)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        logger.info(f"User {user.email} changed their password")
        
        return Response({
            'message': 'Password changed successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Password change error: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred while changing password.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_request(request):
    """
    Request password reset via email
    """
    try:
        email = request.data.get('email')
        
        if not email:
            return Response({
                'error': 'Email is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email, is_active=True)
            
            # Generate password reset token
            # You'll need to implement token generation logic here
            # For now, we'll just acknowledge the request
            
            logger.info(f"Password reset requested for {email}")
            
            return Response({
                'message': 'If an account with this email exists, a password reset link has been sent.'
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            # Don't reveal if email exists or not
            return Response({
                'message': 'If an account with this email exists, a password reset link has been sent.'
            }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Password reset request error: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def user_settings(request):
    """
    Get or update user account settings
    """
    try:
        user = request.user
        
        if request.method == 'GET':
            # Use the UserSettingsSerializer for consistent response
            serializer = UserSettingsSerializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        elif request.method in ['PUT', 'PATCH']:
            # Update settings using the serializer
            partial = request.method == 'PATCH'
            serializer = UserSettingsSerializer(user, data=request.data, partial=partial)
            
            if serializer.is_valid():
                serializer.save()
                
                logger.info(f"User {user.email} updated their settings")
                
                return Response({
                    'message': 'Settings updated successfully',
                    'settings': serializer.data
                }, status=status.HTTP_200_OK)
            
            return Response({
                'error': 'Validation failed',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"User settings error: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred while managing settings.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deactivate_account(request):
    """
    Deactivate user account
    """
    try:
        user = request.user
        password = request.data.get('password')
        
        if not password:
            return Response({
                'error': 'Password confirmation required',
                'detail': 'Please enter your password to confirm account deactivation.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not user.check_password(password):
            return Response({
                'error': 'Invalid password',
                'detail': 'The password you entered is incorrect.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Deactivate account
        user.is_active = False
        user.save()
        
        logger.info(f"User {user.email} deactivated their account")
        
        return Response({
            'message': 'Account deactivated successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Account deactivation error: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred while deactivating account.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)