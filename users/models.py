from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta


class User(AbstractUser):
    """
    Custom User model for the tutor management system.
    Extends Django's AbstractUser to add custom fields and functionality.
    """
    
    # Fix related_name conflicts
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        related_name='custom_user_set',
        related_query_name='custom_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='custom_user_set',
        related_query_name='custom_user',
    )
    
    USER_TYPE_CHOICES = [
        ('admin', 'System Administrator'),
        ('manager', 'Manager'),
        ('tutor', 'Tutor'),
        ('staff', 'Staff Member'),
    ]
    
    # Additional fields
    user_type = models.CharField(
        max_length=10,
        choices=USER_TYPE_CHOICES,
        default='tutor',
        help_text="Type of user in the system"
    )
    
    phone_number = models.CharField(
        max_length=17,
        blank=True,
        null=True,
        help_text="Contact phone number"
    )
    
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        blank=True,
        null=True,
        help_text="User profile picture"
    )
    
    is_verified = models.BooleanField(
        default=False,
        help_text="Designates whether this user has verified their email address"
    )
    
    is_approved = models.BooleanField(
        default=False,
        help_text="Designates whether this user has been approved by an administrator"
    )
    
    last_login_ip = models.GenericIPAddressField(
        blank=True,
        null=True,
        help_text="IP address of last login"
    )
    
    failed_login_attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of consecutive failed login attempts"
    )
    
    locked_until = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Account locked until this datetime due to failed login attempts"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time when the user was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Date and time when the user was last updated"
    )
    
    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['user_type']),
            models.Index(fields=['is_verified', 'is_approved']),
            models.Index(fields=['email']),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.username})" if self.get_full_name() else self.username
    
    @property
    def is_tutor(self):
        """Check if user is a tutor."""
        return self.user_type == 'tutor'
    
    @property
    def is_admin(self):
        """Check if user is an admin."""
        return self.user_type == 'admin'
    
    @property
    def is_manager(self):
        """Check if user is a manager."""
        return self.user_type == 'manager'
    
    @property
    def is_account_locked(self):
        """Check if account is currently locked."""
        if self.locked_until:
            return timezone.now() < self.locked_until
        return False
    
    @property
    def can_login(self):
        """Check if user can login (active, approved, verified, not locked)."""
        return (
            self.is_active and 
            self.is_approved and 
            self.is_verified and 
            not self.is_account_locked
        )
    
    def clean(self):
        """Custom validation for the model."""
        super().clean()
        
        # Ensure email is provided and unique
        if not self.email:
            raise ValidationError("Email address is required.")
        
        # Clean email address
        self.email = self.email.lower().strip()
        
        # Validate user type specific requirements
        if self.user_type == 'admin' and not self.is_staff:
            raise ValidationError("Admin users must have staff privileges.")
    
    def save(self, *args, **kwargs):
        """Override save method to perform validation and setup."""
        self.clean()
        
        # Set staff status for admin users
        if self.user_type == 'admin':
            self.is_staff = True
            self.is_superuser = True
        
        super().save(*args, **kwargs)
    
    def verify_email(self):
        """Mark email as verified."""
        self.is_verified = True
        self.save(update_fields=['is_verified'])
    
    def approve_user(self):
        """Approve the user account."""
        self.is_approved = True
        self.save(update_fields=['is_approved'])
    
    def record_failed_login(self, ip_address=None):
        """Record a failed login attempt."""
        self.failed_login_attempts += 1
        if ip_address:
            self.last_login_ip = ip_address
        
        # Lock account after 5 failed attempts for 30 minutes
        if self.failed_login_attempts >= 5:
            self.locked_until = timezone.now() + timedelta(minutes=30)
        
        self.save(update_fields=['failed_login_attempts', 'last_login_ip', 'locked_until'])
    
    def record_successful_login(self, ip_address=None):
        """Record a successful login."""
        self.failed_login_attempts = 0
        self.locked_until = None
        if ip_address:
            self.last_login_ip = ip_address
        
        self.save(update_fields=['failed_login_attempts', 'locked_until', 'last_login_ip'])
    
    def unlock_account(self):
        """Manually unlock the account."""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save(update_fields=['failed_login_attempts', 'locked_until'])


class TutorProfile(models.Model):
    """
    Extended profile information for tutor users.
    Links the User model with the Tutor model from the tutors app.
    """
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='tutor_profile',
        limit_choices_to={'user_type': 'tutor'},
        help_text="Associated user account"
    )
    
    # This will link to the Tutor model from your tutors app
    # Assuming the tutors app model is accessible
    tutor = models.OneToOneField(
        'tutors.Tutor',  # Adjust this import based on your app structure
        on_delete=models.CASCADE,
        related_name='user_profile',
        blank=True,
        null=True,
        help_text="Associated tutor record"
    )
    
    # Additional profile fields specific to tutor users
    bio = models.TextField(
        max_length=500,
        blank=True,
        help_text="Brief biography or description"
    )
    
    subjects_of_expertise = models.TextField(
        blank=True,
        help_text="Comma-separated list of subjects the tutor specializes in"
    )
    
    years_of_experience = models.PositiveIntegerField(
        default=0,
        help_text="Years of tutoring experience"
    )
    
    hourly_rate = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Hourly tutoring rate"
    )
    
    is_available = models.BooleanField(
        default=True,
        help_text="Whether the tutor is currently available for new students"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tutor_profiles'
        verbose_name = 'Tutor Profile'
        verbose_name_plural = 'Tutor Profiles'
    
    def __str__(self):
        return f"Profile: {self.user.get_full_name() or self.user.username}"
    
    @property
    def subjects_list(self):
        """Return subjects as a list."""
        if self.subjects_of_expertise:
            return [subject.strip() for subject in self.subjects_of_expertise.split(',')]
        return []
    
    def clean(self):
        """Custom validation."""
        super().clean()
        
        # Ensure the linked user is a tutor
        if self.user and self.user.user_type != 'tutor':
            raise ValidationError("TutorProfile can only be linked to users with type 'tutor'.")


class UserSession(models.Model):
    """
    Track user sessions for security purposes.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    
    session_key = models.CharField(
        max_length=40,
        unique=True,
        help_text="Django session key"
    )
    
    ip_address = models.GenericIPAddressField(
        help_text="IP address of the session"
    )
    
    user_agent = models.TextField(
        blank=True,
        help_text="Browser user agent string"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the session is currently active"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_sessions'
        ordering = ['-last_activity']
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'
    
    def __str__(self):
        return f"{self.user.username} - {self.ip_address}"