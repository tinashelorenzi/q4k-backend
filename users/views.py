from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import login
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
    TokenRefreshResponseSerializer
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
            
            # Add tutor profile if user is a tutor
            if user.is_tutor:
                try:
                    tutor_profile = user.tutor_profile
                    response_data['tutor_profile'] = TutorProfileSerializer(tutor_profile).data
                except TutorProfile.DoesNotExist:
                    response_data['tutor_profile'] = None
            
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
        
        # Add tutor profile if user is a tutor
        if user.is_tutor:
            try:
                tutor_profile = user.tutor_profile
                response_data['tutor_profile'] = TutorProfileSerializer(tutor_profile).data
            except TutorProfile.DoesNotExist:
                response_data['tutor_profile'] = None
        
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