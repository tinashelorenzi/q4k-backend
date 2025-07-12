from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from .models import User, TutorProfile


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