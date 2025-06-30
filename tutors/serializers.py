from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify
from decimal import Decimal
import uuid

from .models import Tutor
from users.models import TutorProfile

User = get_user_model()


class TutorSerializer(serializers.ModelSerializer):
    """
    Serializer for the Tutor model.
    """
    tutor_id = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    
    class Meta:
        model = Tutor
        fields = [
            'id',
            'tutor_id',
            'first_name',
            'last_name',
            'full_name',
            'phone_number',
            'email_address',
            'physical_address',
            'highest_qualification',
            'is_active',
            'is_blocked',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'tutor_id', 'full_name', 'status', 'created_at', 'updated_at']
    
    def validate_email_address(self, value):
        """Validate email uniqueness."""
        value = value.lower().strip()
        
        # Check if updating and email hasn't changed
        if self.instance and self.instance.email_address == value:
            return value
        
        # Check for uniqueness
        if Tutor.objects.filter(email_address=value).exists():
            raise serializers.ValidationError("A tutor with this email address already exists.")
        
        return value
    
    def validate_phone_number(self, value):
        """Validate phone number uniqueness."""
        # Check if updating and phone hasn't changed
        if self.instance and self.instance.phone_number == value:
            return value
        
        # Check for uniqueness
        if Tutor.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("A tutor with this phone number already exists.")
        
        return value


class TutorProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for the TutorProfile model.
    """
    subjects_list = serializers.ListField(source='subjects_list', read_only=True)
    
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
        read_only_fields = ['created_at', 'updated_at', 'subjects_list']
    
    def validate_hourly_rate(self, value):
        """Validate hourly rate."""
        if value is not None and value < Decimal('5.00'):
            raise serializers.ValidationError("Hourly rate must be at least $5.00.")
        return value
    
    def validate_years_of_experience(self, value):
        """Validate years of experience."""
        if value < 0:
            raise serializers.ValidationError("Years of experience cannot be negative.")
        if value > 50:
            raise serializers.ValidationError("Years of experience seems unrealistic (max 50 years).")
        return value


class TutorDetailSerializer(TutorSerializer):
    """
    Detailed serializer that includes profile information.
    """
    profile = TutorProfileSerializer(source='user_profile', read_only=True)
    user_info = serializers.SerializerMethodField()
    gigs_count = serializers.SerializerMethodField()
    
    class Meta(TutorSerializer.Meta):
        fields = TutorSerializer.Meta.fields + [
            'profile',
            'user_info',
            'gigs_count',
        ]
    
    def get_user_info(self, obj):
        """Get associated user information if available."""
        try:
            user_profile = obj.user_profile
            if user_profile and user_profile.user:
                user = user_profile.user
                return {
                    'username': user.username,
                    'user_type': user.user_type,
                    'is_verified': user.is_verified,
                    'is_approved': user.is_approved,
                    'last_login': user.last_login,
                }
        except TutorProfile.DoesNotExist:
            pass
        return None
    
    def get_gigs_count(self, obj):
        """Get number of gigs associated with this tutor."""
        return obj.gigs.count()


class CreateTutorSerializer(serializers.Serializer):
    """
    Serializer for creating a new tutor with minimal information.
    """
    first_name = serializers.CharField(max_length=50)
    last_name = serializers.CharField(max_length=50)
    email_address = serializers.EmailField()
    phone_number = serializers.CharField(max_length=17, required=False)
    physical_address = serializers.CharField(max_length=300, required=False)
    highest_qualification = serializers.ChoiceField(
        choices=Tutor.QUALIFICATION_CHOICES,
        required=False,
        default='bachelors'
    )
    
    def validate_email_address(self, value):
        """Validate email uniqueness across both Tutor and User models."""
        value = value.lower().strip()
        
        # Check if email exists in Tutor model
        if Tutor.objects.filter(email_address=value).exists():
            raise serializers.ValidationError("A tutor with this email address already exists.")
        
        # Check if email exists in User model
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email address already exists.")
        
        return value
    
    def validate_phone_number(self, value):
        """Validate phone number if provided."""
        if value and Tutor.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("A tutor with this phone number already exists.")
        return value
    
    def generate_username(self, first_name, last_name, email):
        """Generate a unique username."""
        # Start with a base username
        base_username = f"{first_name.lower()}.{last_name.lower()}"
        base_username = slugify(base_username).replace('-', '.')
        
        # If base username is available, use it
        if not User.objects.filter(username=base_username).exists():
            return base_username
        
        # Otherwise, add a number suffix
        counter = 1
        while True:
            username = f"{base_username}{counter}"
            if not User.objects.filter(username=username).exists():
                return username
            counter += 1
    
    def create(self, validated_data):
        """Create tutor with associated user account and profile."""
        with transaction.atomic():
            # Extract data
            first_name = validated_data['first_name']
            last_name = validated_data['last_name']
            email = validated_data['email_address']
            phone = validated_data.get('phone_number', '+1234567890')  # Dummy phone if not provided
            address = validated_data.get('physical_address', 'Address to be updated')
            qualification = validated_data.get('highest_qualification', 'bachelors')
            
            # Generate username
            username = self.generate_username(first_name, last_name, email)
            
            # Generate temporary password
            temp_password = f"temp{uuid.uuid4().hex[:8]}"
            
            # Create Tutor record
            tutor = Tutor.objects.create(
                first_name=first_name,
                last_name=last_name,
                email_address=email,
                phone_number=phone,
                physical_address=address,
                highest_qualification=qualification,
                is_active=True,
                is_blocked=False,
            )
            
            # Create User account
            user = User.objects.create_user(
                username=username,
                email=email,
                password=temp_password,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone,
                user_type='tutor',
                is_active=True,
                is_verified=False,  # Admin will need to verify
                is_approved=False,  # Admin will need to approve
            )
            
            # Create TutorProfile
            tutor_profile = TutorProfile.objects.create(
                user=user,
                tutor=tutor,
                bio=f"Professional tutor with expertise in various subjects. Profile to be updated.",
                subjects_of_expertise="Mathematics, Science",  # Dummy subjects
                years_of_experience=1,
                hourly_rate=Decimal('25.00'),  # Default rate
                is_available=True,
            )
            
            return {
                'tutor': tutor,
                'user': user,
                'profile': tutor_profile,
                'temp_password': temp_password,
            }


class TutorUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating tutor information.
    """
    
    class Meta:
        model = Tutor
        fields = [
            'first_name',
            'last_name',
            'phone_number',
            'email_address',
            'physical_address',
            'highest_qualification',
        ]
    
    def validate_email_address(self, value):
        """Validate email uniqueness."""
        value = value.lower().strip()
        
        # Check if email hasn't changed
        if self.instance and self.instance.email_address == value:
            return value
        
        # Check for uniqueness
        if Tutor.objects.filter(email_address=value).exists():
            raise serializers.ValidationError("A tutor with this email address already exists.")
        
        return value
    
    def validate_phone_number(self, value):
        """Validate phone number uniqueness."""
        # Check if phone hasn't changed
        if self.instance and self.instance.phone_number == value:
            return value
        
        # Check for uniqueness
        if Tutor.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("A tutor with this phone number already exists.")
        
        return value


class TutorStatusSerializer(serializers.Serializer):
    """
    Serializer for updating tutor status (block/unblock, activate/deactivate).
    """
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_reason(self, value):
        """Validate reason for status change."""
        if value:
            return value.strip()
        return value


class TutorListSerializer(TutorSerializer):
    """
    Simplified serializer for listing tutors.
    """
    gigs_count = serializers.SerializerMethodField()
    last_login = serializers.SerializerMethodField()
    
    class Meta(TutorSerializer.Meta):
        fields = [
            'id',
            'tutor_id',
            'first_name',
            'last_name',
            'full_name',
            'email_address',
            'phone_number',
            'highest_qualification',
            'is_active',
            'is_blocked',
            'status',
            'gigs_count',
            'last_login',
            'created_at',
        ]
    
    def get_gigs_count(self, obj):
        """Get number of gigs."""
        return getattr(obj, 'gigs_count', 0)
    
    def get_last_login(self, obj):
        """Get last login from associated user."""
        try:
            user_profile = obj.user_profile
            if user_profile and user_profile.user:
                return user_profile.user.last_login
        except TutorProfile.DoesNotExist:
            pass
        return None