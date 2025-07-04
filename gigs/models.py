from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal


class Gig(models.Model):
    """
    Model representing a tutoring gig in the management system.
    Created when a client agrees on tutoring services.
    """
    
    # Education level choices
    LEVEL_CHOICES = [
        ('primary', 'Primary School'),
        ('middle', 'Middle School'),
        ('high_school', 'High School'),
        ('college_prep', 'College Preparatory'),
        ('undergraduate', 'Undergraduate'),
        ('graduate', 'Graduate Level'),
        ('professional', 'Professional Development'),
        ('adult_education', 'Adult Education'),
        ('other', 'Other'),
    ]
    
    # Gig status choices
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]
    
    # Priority levels
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    # Core Fields
    tutor = models.ForeignKey(
        'tutors.Tutor',
        on_delete=models.CASCADE,
        related_name='gigs',
        help_text="Assigned tutor for this gig",
        null=True,
        blank=True
    )
    
    title = models.CharField(
        max_length=200,
        help_text="Title or name of the tutoring gig"
    )
    
    subject_name = models.CharField(
        max_length=100,
        help_text="Subject to be tutored (e.g., Mathematics, Physics, English)"
    )
    
    level = models.CharField(
        max_length=20,
        choices=LEVEL_CHOICES,
        help_text="Educational level of the tutoring"
    )
    
    # Financial Fields
    total_tutor_remuneration = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total amount to be paid to the tutor"
    )
    
    total_client_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total amount charged to the client"
    )
    
    # Hours Management
    total_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.50'))],
        help_text="Total planned hours for this gig"
    )
    
    total_hours_remaining = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Hours remaining to complete the gig"
    )
    
    # Additional Fields
    description = models.TextField(
        blank=True,
        help_text="Detailed description of the tutoring requirements"
    )
    
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Current status of the gig"
    )
    
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium',
        help_text="Priority level of the gig"
    )
    
    # Client Information (if you don't have a separate client model yet)
    client_name = models.CharField(
        max_length=100,
        help_text="Name of the client"
    )
    
    client_email = models.EmailField(
        help_text="Client's email address"
    )
    
    client_phone = models.CharField(
        max_length=17,
        blank=True,
        help_text="Client's phone number"
    )
    
    # Dates
    start_date = models.DateField(
        help_text="Planned start date for the tutoring"
    )
    
    end_date = models.DateField(
        help_text="Planned end date for the tutoring"
    )
    
    actual_start_date = models.DateField(
        blank=True,
        null=True,
        help_text="Actual date when tutoring started"
    )
    
    actual_end_date = models.DateField(
        blank=True,
        null=True,
        help_text="Actual date when tutoring ended"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time when the gig was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Date and time when the gig was last updated"
    )
    
    # Additional tracking
    notes = models.TextField(
        blank=True,
        help_text="Internal notes about the gig"
    )
    
    class Meta:
        db_table = 'gigs'
        ordering = ['-created_at']
        verbose_name = 'Gig'
        verbose_name_plural = 'Gigs'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['tutor', 'status']),
            models.Index(fields=['subject_name', 'level']),
            models.Index(fields=['start_date', 'end_date']),
        ]
    
    def __str__(self):
        return f"{self.gig_id} - {self.title} ({self.tutor.full_name if self.tutor else 'Unassigned'})"
    
    @property
    def gig_id(self):
        """
        Returns a formatted gig ID based on the primary key.
        Format: GIG-{padded_id} (e.g., GIG-0001)
        """
        return f"GIG-{self.pk:04d}" if self.pk else "GIG-XXXX"
    
    @property
    def hours_completed(self):
        """Calculate hours completed."""
        if self.total_hours and self.total_hours_remaining:
            return self.total_hours - self.total_hours_remaining
        return 0
    
    @property
    def completion_percentage(self):
        """Calculate completion percentage."""
        if self.total_hours and self.total_hours > 0:
            completed = self.hours_completed
            return round((completed / self.total_hours) * 100, 2)
        return 0
    
    @property
    def hourly_rate_tutor(self):
        """Calculate hourly rate for tutor."""
        if self.total_hours and self.total_hours > 0:
            return round(self.total_tutor_remuneration / self.total_hours, 2)
        return 0
    
    @property
    def hourly_rate_client(self):
        """Calculate hourly rate charged to client."""
        if self.total_hours and self.total_hours > 0:
            return round(self.total_client_fee / self.total_hours, 2)
        return 0
    
    @property
    def profit_margin(self):
        """Calculate profit margin (difference between client fee and tutor remuneration)."""
        if self.total_client_fee and self.total_tutor_remuneration:
            return self.total_client_fee - self.total_tutor_remuneration
        return 0
    
    @property
    def profit_percentage(self):
        """Calculate profit percentage."""
        if self.total_client_fee and self.total_client_fee > 0:
            return round((self.profit_margin / self.total_client_fee) * 100, 2)
        return 0
    
    @property
    def is_overdue(self):
        """Check if gig is overdue."""
        if self.status == 'active' and self.end_date:
            return timezone.now().date() > self.end_date
        return False
    
    @property
    def days_remaining(self):
        """Calculate days remaining until end date."""
        if self.end_date:
            delta = self.end_date - timezone.now().date()
            return delta.days if delta.days >= 0 else 0
        return None
    
    def clean(self):
        """Custom validation for the model."""
        super().clean()
        
        # Validate hours remaining doesn't exceed total hours
        if self.total_hours_remaining > self.total_hours:
            raise ValidationError("Hours remaining cannot exceed total hours.")
        
        # Validate financial fields
        if self.total_client_fee < self.total_tutor_remuneration:
            raise ValidationError("Client fee cannot be less than tutor remuneration.")
        
        # Validate dates
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError("Start date cannot be after end date.")
        
        # Validate actual dates
        if (self.actual_start_date and self.actual_end_date and 
            self.actual_start_date > self.actual_end_date):
            raise ValidationError("Actual start date cannot be after actual end date.")
    
    def save(self, *args, **kwargs):
        """Override save method to perform validation."""
        self.clean()
        super().save(*args, **kwargs)
    
    def start_gig(self):
        """Mark gig as started."""
        if self.status == 'pending':
            self.status = 'active'
            self.actual_start_date = timezone.now().date()
            self.save()
    
    def complete_gig(self):
        """Mark gig as completed."""
        if self.status in ['active', 'on_hold']:
            self.status = 'completed'
            self.actual_end_date = timezone.now().date()
            self.total_hours_remaining = Decimal('0.00')
            self.save()
    
    def cancel_gig(self, reason=""):
        """Cancel the gig."""
        self.status = 'cancelled'
        if reason:
            timestamp = timezone.now().strftime("%Y-%m-%d %H:%M")
            self.notes += f"\n[{timestamp}] Cancellation reason: {reason}"
        self.save()
    
    def put_on_hold(self, reason=""):
        """Put gig on hold."""
        if self.status == 'active':
            self.status = 'on_hold'
            if reason:
                timestamp = timezone.now().strftime("%Y-%m-%d %H:%M")
                self.notes += f"\n[{timestamp}] Put on hold: {reason}"
            self.save()
    
    def resume_gig(self):
        """Resume gig from hold."""
        if self.status == 'on_hold':
            self.status = 'active'
            timestamp = timezone.now().strftime("%Y-%m-%d %H:%M")
            self.notes += f"\n[{timestamp}] Resumed from hold"
            self.save()
    
    def log_hours(self, hours_worked, notes=""):
        """Log hours worked and update remaining hours."""
        if hours_worked > 0 and hours_worked <= self.total_hours_remaining:
            self.total_hours_remaining -= Decimal(str(hours_worked))
            
            # Add notes if provided
            if notes:
                timestamp = timezone.now().strftime("%Y-%m-%d %H:%M")
                self.notes += f"\n[{timestamp}] {hours_worked} hours logged: {notes}"
            
            # Auto-complete if no hours remaining
            if self.total_hours_remaining == 0:
                self.complete_gig()
            else:
                self.save()
            
            return True
        return False


class GigSession(models.Model):
    """
    Model to track individual tutoring sessions within a gig.
    """
    
    gig = models.ForeignKey(
        Gig,
        on_delete=models.CASCADE,
        related_name='sessions',
        help_text="Associated gig"
    )
    
    session_date = models.DateField(
        help_text="Date of the tutoring session"
    )
    
    start_time = models.TimeField(
        help_text="Start time of the session"
    )
    
    end_time = models.TimeField(
        help_text="End time of the session"
    )
    
    hours_logged = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.25'))],
        help_text="Hours logged for this session"
    )
    
    session_notes = models.TextField(
        blank=True,
        help_text="Notes about what was covered in this session"
    )
    
    student_attendance = models.BooleanField(
        default=True,
        help_text="Whether the student attended the session"
    )
    
    # Add verification tracking
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether this session has been verified by an administrator"
    )
    
    verified_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_sessions',
        help_text="Administrator who verified this session"
    )
    
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this session was verified"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'gig_sessions'
        ordering = ['-session_date', '-start_time']
        verbose_name = 'Gig Session'
        verbose_name_plural = 'Gig Sessions'
        indexes = [
            models.Index(fields=['gig', 'session_date']),
            models.Index(fields=['is_verified']),
        ]
    
    def __str__(self):
        return f"{self.gig.gig_id} - {self.session_date} ({self.hours_logged}h)"
    
    @property
    def session_id(self):
        """Get formatted session ID."""
        return f"SES-{self.pk:04d}" if self.pk else "SES-XXXX"
    
    def clean(self):
        """Custom validation."""
        super().clean()
        
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("Start time must be before end time.")
    
    def save(self, *args, **kwargs):
        """Override save to update gig hours only for verified sessions."""
        is_new = self.pk is None
        old_hours = None
        old_verified = False
        
        if not is_new:
            old_session = GigSession.objects.get(pk=self.pk)
            old_hours = old_session.hours_logged
            old_verified = old_session.is_verified
        
        self.clean()
        super().save(*args, **kwargs)
        
        # Only update gig hours for verified sessions
        if self.is_verified:
            if is_new and not old_verified:
                # New verified session - subtract hours from remaining
                self.gig.total_hours_remaining -= self.hours_logged
                self.gig.save()
            elif not is_new and old_verified and old_hours != self.hours_logged:
                # Updated verified session - adjust the difference
                hours_diff = self.hours_logged - old_hours
                self.gig.total_hours_remaining -= hours_diff
                self.gig.save()
            elif not is_new and not old_verified:
                # Session was just verified - subtract hours
                self.gig.total_hours_remaining -= self.hours_logged
                self.gig.save()
        elif not self.is_verified and old_verified:
            # Session was unverified - add hours back
            self.gig.total_hours_remaining += self.hours_logged
            self.gig.save()
    
    def verify(self, verified_by_user):
        """Verify the session."""
        if not self.is_verified:
            self.is_verified = True
            self.verified_by = verified_by_user
            self.verified_at = timezone.now()
            self.save()
            return True
        return False
    
    def unverify(self):
        """Unverify the session."""
        if self.is_verified:
            self.is_verified = False
            self.verified_by = None
            self.verified_at = None
            self.save()
            return True
        return False