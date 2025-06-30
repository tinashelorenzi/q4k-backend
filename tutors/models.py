from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError


class Tutor(models.Model):
    """
    Model representing a tutor in the management system.
    """
    
    # Qualification choices
    QUALIFICATION_CHOICES = [
        ('high_school', 'High School Diploma'),
        ('certificate', 'Certificate'),
        ('diploma', 'Diploma'),
        ('bachelors', "Bachelor's Degree"),
        ('masters', "Master's Degree"),
        ('phd', 'PhD/Doctorate'),
        ('other', 'Other'),
    ]
    
    # Phone number validator
    phone_validator = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    
    # Fields
    first_name = models.CharField(
        max_length=50,
        help_text="Tutor's first name"
    )
    
    last_name = models.CharField(
        max_length=50,
        help_text="Tutor's last name"
    )
    
    phone_number = models.CharField(
        max_length=17,
        validators=[phone_validator],
        unique=True,
        help_text="Contact phone number"
    )
    
    email_address = models.EmailField(
        unique=True,
        help_text="Email address for communication"
    )
    
    physical_address = models.TextField(
        max_length=300,
        help_text="Complete physical address"
    )
    
    highest_qualification = models.CharField(
        max_length=20,
        choices=QUALIFICATION_CHOICES,
        default='bachelors',
        help_text="Highest educational qualification achieved"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether this tutor is currently active"
    )
    
    is_blocked = models.BooleanField(
        default=False,
        help_text="Designates whether this tutor is blocked from the system"
    )
    
    # Timestamp fields
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time when the tutor was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Date and time when the tutor was last updated"
    )
    
    class Meta:
        db_table = 'tutors'
        ordering = ['last_name', 'first_name']
        verbose_name = 'Tutor'
        verbose_name_plural = 'Tutors'
        indexes = [
            models.Index(fields=['email_address']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['is_active', 'is_blocked']),
        ]
    
    def __str__(self):
        return f"{self.full_name} (ID: {self.tutor_id})"
    
    @property
    def tutor_id(self):
        """
        Returns a formatted tutor ID based on the primary key.
        Format: TUT-{padded_id} (e.g., TUT-0001)
        """
        return f"TUT-{self.pk:04d}" if self.pk else "TUT-XXXX"
    
    @property
    def full_name(self):
        """
        Returns the tutor's full name.
        """
        return f"{self.first_name} {self.last_name}".strip()
    
    @property
    def status(self):
        """
        Returns the current status of the tutor.
        """
        if self.is_blocked:
            return "Blocked"
        elif self.is_active:
            return "Active"
        else:
            return "Inactive"
    
    def clean(self):
        """
        Custom validation for the model.
        """
        super().clean()
        
        # Ensure email and phone are provided
        if not self.email_address:
            raise ValidationError("Email address is required.")
        
        if not self.phone_number:
            raise ValidationError("Phone number is required.")
        
        # Clean email address
        self.email_address = self.email_address.lower().strip()
        
        # Clean names
        self.first_name = self.first_name.strip().title()
        self.last_name = self.last_name.strip().title()
    
    def save(self, *args, **kwargs):
        """
        Override save method to perform validation.
        """
        self.clean()
        super().save(*args, **kwargs)
    
    def deactivate(self):
        """
        Deactivate the tutor.
        """
        self.is_active = False
        self.save()
    
    def activate(self):
        """
        Activate the tutor.
        """
        self.is_active = True
        self.save()
    
    def block(self):
        """
        Block the tutor.
        """
        self.is_blocked = True
        self.is_active = False
        self.save()
    
    def unblock(self):
        """
        Unblock the tutor.
        """
        self.is_blocked = False
        self.save()