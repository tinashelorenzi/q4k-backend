from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from datetime import datetime

from .models import Gig, GigSession
from tutors.models import Tutor
from tutors.serializers import TutorSerializer


class GigSessionSerializer(serializers.ModelSerializer):
    """
    Serializer for GigSession model.
    """
    session_id = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()
    verified_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = GigSession
        fields = [
            'id',
            'session_id',
            'gig',
            'session_date',
            'start_time',
            'end_time',
            'hours_logged',
            'duration_display',
            'session_notes',
            'student_attendance',
            'is_verified',
            'verified_by',
            'verified_by_name',
            'verified_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'session_id', 'duration_display', 'is_verified', 
            'verified_by', 'verified_by_name', 'verified_at', 'created_at', 'updated_at'
        ]
    
    def get_session_id(self, obj):
        """Get formatted session ID."""
        return f"SES-{obj.pk:04d}" if obj.pk else "SES-XXXX"
    
    def get_duration_display(self, obj):
        """Get time duration display."""
        if obj.start_time and obj.end_time:
            return f"{obj.start_time} - {obj.end_time}"
        return None
    
    def get_verified_by_name(self, obj):
        """Get name of user who verified the session."""
        if obj.verified_by:
            return obj.verified_by.get_full_name() or obj.verified_by.username
        return None
    
    def validate(self, attrs):
        """Custom validation for session data."""
        start_time = attrs.get('start_time')
        end_time = attrs.get('end_time')
        hours_logged = attrs.get('hours_logged')
        session_date = attrs.get('session_date')
        
        # Validate time range
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError("Start time must be before end time.")
        
        # Validate session date
        if session_date and session_date > timezone.now().date():
            raise serializers.ValidationError("Session date cannot be in the future.")
        
        # Validate hours logged
        if hours_logged and hours_logged <= 0:
            raise serializers.ValidationError("Hours logged must be greater than 0.")
        
        if hours_logged and hours_logged > Decimal('24.00'):
            raise serializers.ValidationError("Hours logged cannot exceed 24 hours per session.")
        
        return attrs


class GigSessionCreateSerializer(GigSessionSerializer):
    """
    Serializer for creating gig sessions.
    """
    
    def validate(self, attrs):
        """Additional validation for creating sessions."""
        attrs = super().validate(attrs)
        
        gig = attrs.get('gig')
        hours_logged = attrs.get('hours_logged')
        
        # Check if gig is active
        if gig and gig.status != 'active':
            raise serializers.ValidationError("Can only create sessions for active gigs.")
        
        # Check if hours exceed remaining hours
        if gig and hours_logged and hours_logged > gig.total_hours_remaining:
            raise serializers.ValidationError(
                f"Hours logged ({hours_logged}) cannot exceed remaining hours ({gig.total_hours_remaining})."
            )
        
        return attrs


class GigSessionDetailSerializer(GigSessionSerializer):
    """
    Detailed serializer for session with gig information.
    """
    gig_info = serializers.SerializerMethodField()
    
    class Meta(GigSessionSerializer.Meta):
        fields = GigSessionSerializer.Meta.fields + ['gig_info']
    
    def get_gig_info(self, obj):
        """Get basic gig information."""
        return {
            'gig_id': obj.gig.gig_id,
            'title': obj.gig.title,
            'status': obj.gig.status,
            'client_name': obj.gig.client_name,
        }


class GigSerializer(serializers.ModelSerializer):
    """
    Serializer for the Gig model.
    """
    gig_id = serializers.CharField(read_only=True)
    tutor_name = serializers.SerializerMethodField()
    completion_percentage = serializers.ReadOnlyField()
    hours_completed = serializers.ReadOnlyField()
    profit_margin = serializers.ReadOnlyField()
    profit_percentage = serializers.ReadOnlyField()
    hourly_rate_tutor = serializers.ReadOnlyField()
    hourly_rate_client = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    days_remaining = serializers.ReadOnlyField()
    
    class Meta:
        model = Gig
        fields = [
            'id',
            'gig_id',
            'tutor',
            'tutor_name',
            'title',
            'subject_name',
            'level',
            'total_tutor_remuneration',
            'total_client_fee',
            'total_hours',
            'total_hours_remaining',
            'hours_completed',
            'completion_percentage',
            'hourly_rate_tutor',
            'hourly_rate_client',
            'profit_margin',
            'profit_percentage',
            'description',
            'status',
            'priority',
            'client_name',
            'client_email',
            'client_phone',
            'start_date',
            'end_date',
            'actual_start_date',
            'actual_end_date',
            'is_overdue',
            'days_remaining',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'gig_id', 'tutor_name', 'completion_percentage', 'hours_completed',
            'profit_margin', 'profit_percentage', 'hourly_rate_tutor', 'hourly_rate_client',
            'is_overdue', 'days_remaining', 'created_at', 'updated_at'
        ]
    
    def get_tutor_name(self, obj):
        """Get tutor full name."""
        return obj.tutor.full_name if obj.tutor else None
    
    def validate(self, attrs):
        """Custom validation for gig data."""
        total_hours = attrs.get('total_hours')
        total_hours_remaining = attrs.get('total_hours_remaining')
        total_client_fee = attrs.get('total_client_fee')
        total_tutor_remuneration = attrs.get('total_tutor_remuneration')
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        # Use existing values if not provided (for updates)
        if self.instance:
            total_hours = total_hours if total_hours is not None else self.instance.total_hours
            total_hours_remaining = total_hours_remaining if total_hours_remaining is not None else self.instance.total_hours_remaining
            total_client_fee = total_client_fee if total_client_fee is not None else self.instance.total_client_fee
            total_tutor_remuneration = total_tutor_remuneration if total_tutor_remuneration is not None else self.instance.total_tutor_remuneration
            start_date = start_date if start_date is not None else self.instance.start_date
            end_date = end_date if end_date is not None else self.instance.end_date
        
        # Validate hours
        if total_hours_remaining and total_hours and total_hours_remaining > total_hours:
            raise serializers.ValidationError("Hours remaining cannot exceed total hours.")
        
        # Validate financial fields
        if total_client_fee and total_tutor_remuneration and total_client_fee < total_tutor_remuneration:
            raise serializers.ValidationError("Client fee cannot be less than tutor remuneration.")
        
        # Validate dates
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError("Start date cannot be after end date.")
        
        return attrs


class GigDetailSerializer(GigSerializer):
    """
    Detailed serializer with tutor information and sessions.
    """
    tutor_details = TutorSerializer(source='tutor', read_only=True)
    sessions_count = serializers.SerializerMethodField()
    recent_sessions = serializers.SerializerMethodField()
    
    class Meta(GigSerializer.Meta):
        fields = GigSerializer.Meta.fields + [
            'tutor_details',
            'sessions_count',
            'recent_sessions',
        ]
    
    def get_sessions_count(self, obj):
        """Get total number of sessions."""
        return obj.sessions.count()
    
    def get_recent_sessions(self, obj):
        """Get 5 most recent sessions."""
        recent_sessions = obj.sessions.all()[:5]
        return GigSessionSerializer(recent_sessions, many=True).data


class GigCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new gigs.
    """
    
    class Meta:
        model = Gig
        fields = [
            'tutor',
            'title',
            'subject_name',
            'level',
            'total_tutor_remuneration',
            'total_client_fee',
            'total_hours',
            'description',
            'priority',
            'client_name',
            'client_email',
            'client_phone',
            'start_date',
            'end_date',
            'notes',
        ]
    
    def validate(self, attrs):
        """Validation for creating gigs."""
        attrs = super().validate(attrs)
        
        # Set total_hours_remaining to total_hours
        attrs['total_hours_remaining'] = attrs['total_hours']
        
        return attrs


class GigUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating gig information.
    """
    
    class Meta:
        model = Gig
        fields = [
            'title',
            'subject_name',
            'level',
            'total_tutor_remuneration',
            'total_client_fee',
            'total_hours',
            'description',
            'priority',
            'client_name',
            'client_email',
            'client_phone',
            'start_date',
            'end_date',
            'notes',
        ]
    
    def validate_total_hours(self, value):
        """Validate total hours change."""
        if self.instance:
            hours_completed = self.instance.hours_completed
            if value < hours_completed:
                raise serializers.ValidationError(
                    f"Total hours ({value}) cannot be less than hours already completed ({hours_completed})."
                )
        return value


class GigAssignmentSerializer(serializers.Serializer):
    """
    Serializer for assigning gigs to tutors.
    """
    tutor_id = serializers.IntegerField()
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_tutor_id(self, value):
        """Validate tutor exists and is active."""
        try:
            tutor = Tutor.objects.get(pk=value)
            if not tutor.is_active:
                raise serializers.ValidationError("Cannot assign gig to inactive tutor.")
            if tutor.is_blocked:
                raise serializers.ValidationError("Cannot assign gig to blocked tutor.")
            return value
        except Tutor.DoesNotExist:
            raise serializers.ValidationError("Tutor not found.")


class GigStatusChangeSerializer(serializers.Serializer):
    """
    Serializer for changing gig status.
    """
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_reason(self, value):
        """Clean reason."""
        if value:
            return value.strip()
        return value


class GigHoursAdjustmentSerializer(serializers.Serializer):
    """
    Serializer for adjusting gig hours.
    """
    hours_to_subtract = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=0.25)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_hours_to_subtract(self, value):
        """Validate hours to subtract."""
        gig = self.context.get('gig')
        if gig and value > gig.total_hours_remaining:
            raise serializers.ValidationError(
                f"Cannot subtract {value} hours. Only {gig.total_hours_remaining} hours remaining."
            )
        return value


class GigListSerializer(GigSerializer):
    """
    Simplified serializer for listing gigs.
    """
    sessions_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Gig
        fields = [
            'id',
            'gig_id',
            'tutor',
            'tutor_name',
            'title',
            'subject_name',
            'level',
            'status',
            'priority',
            'client_name',
            'total_hours',
            'total_hours_remaining',
            'completion_percentage',
            'start_date',
            'end_date',
            'is_overdue',
            'days_remaining',
            'sessions_count',
            'created_at',
        ]
    
    def get_sessions_count(self, obj):
        """Get session count."""
        return getattr(obj, 'sessions_count', 0)


class SessionVerificationSerializer(serializers.Serializer):
    """
    Serializer for verifying/unverifying sessions.
    """
    verified = serializers.BooleanField()
    verification_notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate(self, attrs):
        """Validation for session verification."""
        session = self.context.get('session')
        verified = attrs.get('verified')
        
        if not session:
            raise serializers.ValidationError("Session not found in context.")
        
        # Check if gig is active
        if session.gig.status != 'active':
            raise serializers.ValidationError("Can only verify sessions for active gigs.")
        
        # If verifying, check if enough hours remain
        if verified and session.hours_logged > session.gig.total_hours_remaining:
            raise serializers.ValidationError(
                f"Cannot verify session. Hours logged ({session.hours_logged}) "
                f"exceed remaining hours ({session.gig.total_hours_remaining})."
            )
        
        return attrs