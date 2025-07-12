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
from django.db import transaction
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.core.exceptions import ValidationError as DjangoValidationError
import logging

from .models import User, TutorProfile
from .serializers import (
    LoginSerializer,
    LoginResponseSerializer,
    UserSerializer,
    TutorProfileSerializer,
    LogoutSerializer,
    TokenRefreshResponseSerializer,
    UserSettingsSerializer,
    BatchTutorImportSerializer,
    AccountSetupSerializer,
    TokenVerificationSerializer,
    AccountSetupToken,
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

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_tutor_import(request):
    """
    API endpoint for batch tutor import via CSV content.
    
    Expects JSON payload with:
    {
        "csv_content": "first_name,last_name,email\nJohn,Doe,john@example.com\n..."
    }
    
    Returns summary of import results.
    """
    # Check if user has permission (you can customize this)
    if not request.user.user_type in ['admin', 'manager']:
        return Response(
            {'error': 'You do not have permission to perform batch imports.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = BatchTutorImportSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    tutors_data = serializer.validated_data['csv_content']
    
    try:
        with transaction.atomic():
            # Create account setup tokens for all tutors
            tokens_created = []
            
            for tutor_data in tutors_data:
                token = AccountSetupToken.objects.create(
                    email=tutor_data['email'],
                    first_name=tutor_data['first_name'],
                    last_name=tutor_data['last_name'],
                    tutor_id=tutor_data['tutor_id']
                )
                tokens_created.append(token)
            
            # Send emails to all tutors
            successful_emails = []
            failed_emails = []
            
            for token in tokens_created:
                try:
                    if send_account_setup_email(token):
                        successful_emails.append(token.email)
                    else:
                        failed_emails.append(token.email)
                except Exception as e:
                    logger.error(f"Error sending email to {token.email}: {str(e)}")
                    failed_emails.append(token.email)
            
            # Send summary email to admin
            try:
                send_batch_import_summary_email(
                    admin_email=request.user.email,
                    total_count=len(tutors_data),
                    success_count=len(successful_emails),
                    failed_emails=failed_emails if failed_emails else None
                )
            except Exception as e:
                logger.error(f"Failed to send summary email: {str(e)}")
            
            return Response({
                'message': 'Batch import completed',
                'total_tutors': len(tutors_data),
                'successful_emails': len(successful_emails),
                'failed_emails': len(failed_emails),
                'successful_emails_list': successful_emails,
                'failed_emails_list': failed_emails,
            }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        logger.error(f"Batch import failed: {str(e)}")
        return Response(
            {'error': 'An error occurred during batch import. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([AllowAny])
def verify_setup_token(request):
    """
    API endpoint to verify a setup token and get basic info.
    
    Query params: ?token=<token_value>
    
    Returns token validity and associated user info.
    """
    token = request.query_params.get('token')
    if not token:
        return Response(
            {'error': 'Token parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    serializer = TokenVerificationSerializer(data={'token': token})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        token_obj = AccountSetupToken.objects.get(token=token)
        return Response({
            'valid': True,
            'first_name': token_obj.first_name,
            'last_name': token_obj.last_name,
            'email': token_obj.email,
            'tutor_id': token_obj.tutor_id,
            'expires_at': token_obj.expires_at,
        })
    except AccountSetupToken.DoesNotExist:
        return Response(
            {'error': 'Invalid token'},
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['POST'])
@permission_classes([AllowAny])
def complete_account_setup(request):
    """
    API endpoint to complete account setup using a token.
    
    Expects JSON payload with:
    {
        "token": "token_value",
        "password": "secure_password",
        "confirm_password": "secure_password",
        "phone_number": "+1234567890", // optional
        "physical_address": "123 Main St..." // optional
    }
    
    Creates User, Tutor, and TutorProfile records.
    """
    serializer = AccountSetupSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    token_obj = serializer.validated_data['token_obj']
    
    try:
        with transaction.atomic():
            # Create User account
            user = User.objects.create_user(
                username=token_obj.email,  # Use email as username
                email=token_obj.email,
                first_name=token_obj.first_name,
                last_name=token_obj.last_name,
                password=serializer.validated_data['password'],
                user_type='tutor',
                is_verified=True,  # Since they came from admin import
                is_approved=True,  # Since they came from admin import
            )
            
            # Create Tutor record
            tutor = Tutor.objects.create(
                first_name=token_obj.first_name,
                last_name=token_obj.last_name,
                email_address=token_obj.email,
                phone_number=serializer.validated_data.get('phone_number', ''),
                physical_address=serializer.validated_data.get('physical_address', ''),
                tutor_id=token_obj.tutor_id  # Use the tutor_id from CSV
            )
            
            # Create TutorProfile
            tutor_profile = TutorProfile.objects.create(
                user=user,
                tutor=tutor,
                bio='',  # They can fill this later
                subjects_of_expertise='',  # They can fill this later
                years_of_experience=0,
                hourly_rate=None,
                is_available=True,
            )
            
            # Mark token as used
            token_obj.is_used = True
            token_obj.used_at = timezone.now()
            token_obj.save()
            
            # Generate JWT tokens for immediate login
            tokens = get_tokens_for_user(user)
            
            return Response({
                'message': 'Account setup completed successfully',
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'user_type': user.user_type,
                },
                'tutor': {
                    'id': tutor.id,
                    'tutor_id': tutor.tutor_id,
                    'full_name': tutor.full_name,
                },
                'tokens': tokens,
            }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        logger.error(f"Account setup failed for {token_obj.email}: {str(e)}")
        return Response(
            {'error': 'An error occurred during account setup. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def batch_import_history(request):
    """
    API endpoint to get batch import history.
    Shows pending and used tokens.
    """
    # Check permissions
    if not request.user.user_type in ['admin', 'manager']:
        return Response(
            {'error': 'You do not have permission to view batch import history.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get query parameters
    status_filter = request.query_params.get('status', 'all')  # all, pending, used, expired
    
    # Base queryset
    queryset = AccountSetupToken.objects.all()
    
    # Apply filters
    if status_filter == 'pending':
        queryset = queryset.filter(is_used=False, expires_at__gt=timezone.now())
    elif status_filter == 'used':
        queryset = queryset.filter(is_used=True)
    elif status_filter == 'expired':
        queryset = queryset.filter(is_used=False, expires_at__lte=timezone.now())
    
    # Get paginated results
    from django.core.paginator import Paginator
    
    paginator = Paginator(queryset, 20)  # 20 items per page
    page_number = request.query_params.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Serialize data
    tokens_data = []
    for token in page_obj:
        tokens_data.append({
            'id': token.id,
            'email': token.email,
            'first_name': token.first_name,
            'last_name': token.last_name,
            'tutor_id': token.tutor_id,
            'is_used': token.is_used,
            'is_expired': token.is_expired(),
            'created_at': token.created_at,
            'expires_at': token.expires_at,
            'used_at': token.used_at,
        })
    
    return Response({
        'tokens': tokens_data,
        'pagination': {
            'current_page': page_obj.number,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        }
    })