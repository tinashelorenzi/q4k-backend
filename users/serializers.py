from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from .models import User, TutorProfile
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
import csv
import io
from .models import AccountSetupToken


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login with email and password.
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            # Normalize email
            email = email.lower().strip()
            
            # Try to get user by email
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    'Invalid email or password.',
                    code='invalid_credentials'
                )
            
            # Check if account is locked
            if user.is_account_locked:
                raise serializers.ValidationError(
                    f'Account is locked until {user.locked_until.strftime("%Y-%m-%d %H:%M:%S")}. '
                    'Please try again later or contact support.',
                    code='account_locked'
                )
            
            # Check if user can login (active, verified, approved)
            if not user.can_login:
                error_messages = []
                if not user.is_active:
                    error_messages.append('Account is inactive.')
                if not user.is_verified:
                    error_messages.append('Email address is not verified.')
                if not user.is_approved:
                    error_messages.append('Account is pending approval.')
                
                raise serializers.ValidationError(
                    ' '.join(error_messages),
                    code='account_restricted'
                )
            
            # Authenticate user
            user = authenticate(request=self.context.get('request'),
                              username=user.username, password=password)
            
            if not user:
                # Record failed login attempt
                try:
                    failed_user = User.objects.get(email=email)
                    request = self.context.get('request')
                    ip_address = None
                    if request:
                        ip_address = self.get_client_ip(request)
                    failed_user.record_failed_login(ip_address)
                except User.DoesNotExist:
                    pass
                
                raise serializers.ValidationError(
                    'Invalid email or password.',
                    code='invalid_credentials'
                )
            
            attrs['user'] = user
            return attrs
        
        raise serializers.ValidationError(
            'Must include "email" and "password".',
            code='required_fields'
        )
    
    def get_client_ip(self, request):
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model data.
    """

    full_name = serializers.CharField(source='get_full_name', read_only=True)
    user_type_display = serializers.CharField(source='get_user_type_display', read_only=True)
    language_display = serializers.CharField(source='get_language_preference_display', read_only=True)
    theme_display = serializers.CharField(source='get_theme_preference_display', read_only=True)
    date_format_display = serializers.CharField(source='get_date_format_display', read_only=True)
    time_format_display = serializers.CharField(source='get_time_format_display', read_only=True)
    
    class Meta:
        model = User
        fields = [
            # Basic Info
            'id', 'username', 'first_name', 'last_name', 'full_name', 'email', 
            'phone_number', 'profile_picture',
            
            # Account Status
            'user_type', 'user_type_display', 'is_active', 'is_verified', 
            'is_approved', 'is_staff', 'is_superuser',
            
            # Notification Settings
            'email_notifications', 'sms_notifications', 'push_notifications', 
            'marketing_emails', 'login_notifications',
            
            # Preferences
            'language_preference', 'language_display', 'timezone', 
            'date_format', 'date_format_display', 'time_format', 'time_format_display',
            'theme_preference', 'theme_display',
            
            # Privacy Settings
            'profile_visible', 'show_online_status', 'show_email', 'show_phone',
            
            # Security Settings
            'two_factor_enabled', 'session_timeout',
            
            # Timestamps
            'last_login', 'date_joined', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'full_name', 'user_type_display', 'language_display', 
            'theme_display', 'date_format_display', 'time_format_display',
            'is_staff', 'is_superuser', 'last_login', 'date_joined', 
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'password': {'write_only': True},
        }
    
    def validate_email(self, value):
        """Validate email address."""
        user = self.instance
        if user and user.email == value:
            return value
            
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email address is already in use.")
        return value
    
    def validate_session_timeout(self, value):
        """Validate session timeout value."""
        if value < 0:
            raise serializers.ValidationError("Session timeout cannot be negative.")
        if value > 43200:  # 30 days in minutes
            raise serializers.ValidationError("Session timeout cannot exceed 30 days.")
        return value

    def update(self, instance, validated_data):
        """Custom update method to handle password changes."""
        password = validated_data.pop('password', None)
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Handle password separately if provided
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance



class TutorProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for TutorProfile model.
    """
    subjects_list = serializers.ListField(read_only=True)
    
    class Meta:
        model = TutorProfile
        fields = [
            'bio',
            'subjects_of_expertise',
            'subjects_list',
            'years_of_experience',
            'hourly_rate',
            'is_available',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class LoginResponseSerializer(serializers.Serializer):
    """
    Serializer for login response data.
    """
    access_token = serializers.CharField(read_only=True)
    refresh_token = serializers.CharField(read_only=True)
    user = UserSerializer(read_only=True)
    tutor_profile = TutorProfileSerializer(read_only=True, required=False)
    message = serializers.CharField(read_only=True)


class TokenRefreshResponseSerializer(serializers.Serializer):
    """
    Serializer for token refresh response.
    """
    access_token = serializers.CharField(read_only=True)
    message = serializers.CharField(read_only=True)


class LogoutSerializer(serializers.Serializer):
    """
    Serializer for logout request.
    """
    refresh_token = serializers.CharField(required=True)
    
    def validate_refresh_token(self, value):
        if not value:
            raise serializers.ValidationError("Refresh token is required.")
        return value


class UserSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer specifically for user settings (subset of UserSerializer).
    Used for the settings endpoints.
    """
    language_display = serializers.CharField(source='get_language_preference_display', read_only=True)
    theme_display = serializers.CharField(source='get_theme_preference_display', read_only=True)
    date_format_display = serializers.CharField(source='get_date_format_display', read_only=True)
    time_format_display = serializers.CharField(source='get_time_format_display', read_only=True)
    
    class Meta:
        model = User
        fields = [
            # Notification Settings
            'email_notifications', 'sms_notifications', 'push_notifications', 
            'marketing_emails', 'login_notifications',
            
            # Preferences
            'language_preference', 'language_display', 'timezone', 
            'date_format', 'date_format_display', 'time_format', 'time_format_display',
            'theme_preference', 'theme_display',
            
            # Privacy Settings
            'profile_visible', 'show_online_status', 'show_email', 'show_phone',
            
            # Security Settings
            'two_factor_enabled', 'session_timeout',
        ]

class UserBasicSerializer(serializers.ModelSerializer):
    """
    Basic user serializer for public profile views.
    Respects privacy settings.
    """
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'full_name', 'profile_picture', 'user_type'
        ]
    
    def to_representation(self, instance):
        """Custom representation that respects privacy settings."""
        data = super().to_representation(instance)
        
        # Only include email if user allows it
        if instance.show_email:
            data['email'] = instance.email
        
        # Only include phone if user allows it
        if instance.show_phone:
            data['phone_number'] = instance.phone_number
            
        return data

class BatchTutorImportSerializer(serializers.Serializer):
    """
    Serializer for batch tutor import via CSV content.
    """
    csv_content = serializers.CharField(
        help_text="CSV content with tutor data (name, email columns required)"
    )
    
    def validate_csv_content(self, value):
        """Validate CSV content and extract tutor data."""
        if not value.strip():
            raise serializers.ValidationError("CSV content cannot be empty.")
        
        try:
            # Parse CSV content
            csv_reader = csv.DictReader(io.StringIO(value.strip()))
            
            # Check if required headers exist
            headers = csv_reader.fieldnames
            if not headers:
                raise serializers.ValidationError("CSV must have headers.")
            
            # Convert headers to lowercase for case-insensitive matching
            headers_lower = [h.lower().strip() for h in headers]
            
            # Check for required columns (flexible naming)
            required_mappings = {
                'first_name': ['first_name', 'firstname', 'first name', 'name'],
                'last_name': ['last_name', 'lastname', 'last name', 'surname'],
                'email': ['email', 'email_address', 'email address', 'e-mail'],
                'tutor_id': ['tutor_id', 'tutorid', 'tutor id', 'id', 'tutor_code', 'code']
            }
            
            field_mapping = {}
            for required_field, possible_names in required_mappings.items():
                found = False
                for possible_name in possible_names:
                    if possible_name in headers_lower:
                        # Get the original header name
                        original_header = headers[headers_lower.index(possible_name)]
                        field_mapping[required_field] = original_header
                        found = True
                        break
                
                if not found:
                    raise serializers.ValidationError(
                        f"Required column not found. Need one of: {', '.join(possible_names)}"
                    )
            
            # Parse and validate rows
            tutors_data = []
            row_number = 1
            
            for row in csv_reader:
                row_number += 1
                
                try:
                    # Extract data using field mapping
                    first_name = row[field_mapping['first_name']].strip()
                    last_name = row[field_mapping['last_name']].strip()
                    email = row[field_mapping['email']].strip().lower()
                    tutor_id = row[field_mapping['tutor_id']].strip().upper()  # Standardize to uppercase
                    
                    # Validate required fields
                    if not first_name:
                        raise serializers.ValidationError(f"Row {row_number}: First name is required.")
                    if not last_name:
                        raise serializers.ValidationError(f"Row {row_number}: Last name is required.")
                    if not email:
                        raise serializers.ValidationError(f"Row {row_number}: Email is required.")
                    if not tutor_id:
                        raise serializers.ValidationError(f"Row {row_number}: Tutor ID is required.")
                    
                    # Validate email format
                    try:
                        validate_email(email)
                    except DjangoValidationError:
                        raise serializers.ValidationError(f"Row {row_number}: Invalid email format: {email}")
                    
                    # Check for duplicates in current batch
                    if any(t['email'] == email for t in tutors_data):
                        raise serializers.ValidationError(f"Row {row_number}: Duplicate email in CSV: {email}")
                    
                    if any(t['tutor_id'] == tutor_id for t in tutors_data):
                        raise serializers.ValidationError(f"Row {row_number}: Duplicate tutor ID in CSV: {tutor_id}")
                    
                    # Check if email already exists in system
                    from django.contrib.auth import get_user_model
                    from tutors.models import Tutor
                    User = get_user_model()
                    
                    if User.objects.filter(email=email).exists():
                        raise serializers.ValidationError(f"Row {row_number}: User with email {email} already exists.")
                    
                    if Tutor.objects.filter(email_address=email).exists():
                        raise serializers.ValidationError(f"Row {row_number}: Tutor with email {email} already exists.")
                    
                    if Tutor.objects.filter(tutor_id=tutor_id).exists():
                        raise serializers.ValidationError(f"Row {row_number}: Tutor with ID {tutor_id} already exists.")
                    
                    if AccountSetupToken.objects.filter(email=email, is_used=False).exists():
                        raise serializers.ValidationError(f"Row {row_number}: Pending setup token for {email} already exists.")
                    
                    if AccountSetupToken.objects.filter(tutor_id=tutor_id, is_used=False).exists():
                        raise serializers.ValidationError(f"Row {row_number}: Pending setup token for tutor ID {tutor_id} already exists.")
                    
                    tutors_data.append({
                        'first_name': first_name,
                        'last_name': last_name,
                        'email': email,
                        'tutor_id': tutor_id
                    })
                    
                except KeyError as e:
                    raise serializers.ValidationError(f"Row {row_number}: Missing column data.")
            
            if not tutors_data:
                raise serializers.ValidationError("No valid tutor data found in CSV.")
            
            return tutors_data
            
        except csv.Error as e:
            raise serializers.ValidationError(f"CSV parsing error: {str(e)}")

class AccountSetupSerializer(serializers.Serializer):
    """
    Serializer for account setup using token.
    """
    token = serializers.CharField(max_length=64)
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    
    # Optional additional fields
    phone_number = serializers.CharField(max_length=17, required=False, allow_blank=True)
    physical_address = serializers.CharField(max_length=300, required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate password confirmation and token."""
        # Check password confirmation
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        
        # Validate token
        try:
            token_obj = AccountSetupToken.objects.get(token=data['token'])
            if not token_obj.is_valid():
                if token_obj.is_used:
                    raise serializers.ValidationError("This setup link has already been used.")
                else:
                    raise serializers.ValidationError("This setup link has expired.")
            data['token_obj'] = token_obj
        except AccountSetupToken.DoesNotExist:
            raise serializers.ValidationError("Invalid setup token.")
        
        return data
    
    def validate_password(self, value):
        """Validate password strength."""
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError
        
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        
        return value


class TokenVerificationSerializer(serializers.Serializer):
    """
    Serializer for verifying a setup token.
    """
    token = serializers.CharField(max_length=64)
    
    def validate_token(self, value):
        """Validate token exists and is valid."""
        try:
            token_obj = AccountSetupToken.objects.get(token=value)
            if not token_obj.is_valid():
                if token_obj.is_used:
                    raise serializers.ValidationError("This setup link has already been used.")
                else:
                    raise serializers.ValidationError("This setup link has expired.")
            return value
        except AccountSetupToken.DoesNotExist:
            raise serializers.ValidationError("Invalid setup token.")