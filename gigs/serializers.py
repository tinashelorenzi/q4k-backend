from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from datetime import datetime

from .models import Gig, GigSession, OnlineSession, OnlineMeetingRequest
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
        """Get basic gig information including tutor details."""
        gig_info = {
            'gig_id': obj.gig.gig_id,
            'title': obj.gig.title,
            'status': obj.gig.status,
            'client_name': obj.gig.client_name,
        }
        
        # Add tutor information if available
        if obj.gig.tutor:
            gig_info['tutor'] = {
                'id': obj.gig.tutor.id,
                'tutor_id': obj.gig.tutor.tutor_id,
                'full_name': obj.gig.tutor.full_name,
                'email_address': obj.gig.tutor.email_address,
                'phone_number': obj.gig.tutor.phone_number,
            }
        else:
            gig_info['tutor'] = None
            
        return gig_info


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
    tutor_details = serializers.SerializerMethodField()
    
    class Meta:
        model = Gig
        fields = [
            'id',
            'gig_id',
            'tutor',
            'tutor_name',
            'tutor_details',
            'title',
            'subject_name',
            'level',
            'status',
            'priority',
            'client_name',
            'total_hours',
            'total_hours_remaining',
            'hours_completed',  # Added for progress calculation
            'completion_percentage',
            'hourly_rate_tutor',  # Added for earnings calculation
            'hourly_rate_client',  # Added for reference
            'total_tutor_remuneration',  # Added for reference
            'total_client_fee',  # Added for revenue calculation
            'profit_margin',  # Added for profit calculation
            'start_date',
            'end_date',
            'is_overdue',
            'days_remaining',
            'sessions_count',
            'created_at',
        ]
    
    def get_tutor_details(self, obj):
        """Get full tutor details for online session creation."""
        if obj.tutor:
            return {
                'id': obj.tutor.id,
                'tutor_id': obj.tutor.tutor_id,
                'full_name': obj.tutor.full_name,
                'email_address': obj.tutor.email_address,
                'phone_number': obj.tutor.phone_number,
            }
        return None
    
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
        
        # Note: We allow verification of sessions even for completed/paused gigs
        # because admins may verify sessions at the end of the month after the gig period
        
        # If verifying, check if enough hours remain
        if verified and not session.is_verified and session.hours_logged > session.gig.total_hours_remaining:
            raise serializers.ValidationError(
                f"Cannot verify session. Hours logged ({session.hours_logged}) "
                f"exceed remaining hours ({session.gig.total_hours_remaining})."
            )
        
        return attrs

class OnlineSessionSerializer(serializers.ModelSerializer):
    """
    Serializer for OnlineSession model.
    """
    session_id = serializers.CharField(read_only=True)
    digital_samba_url = serializers.CharField(read_only=True)
    meeting_url = serializers.CharField(read_only=True)
    tutor_meeting_url = serializers.CharField(read_only=True)
    client_meeting_url = serializers.CharField(read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)
    is_ongoing = serializers.BooleanField(read_only=True)
    time_remaining_minutes = serializers.IntegerField(read_only=True)
    
    # Related fields
    gig_info = serializers.SerializerMethodField()
    tutor_info = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        from .models import OnlineSession
        model = OnlineSession
        fields = [
            'id', 'session_id', 'gig', 'tutor', 'meeting_code', 'pin_code',
            'room_name', 'digital_samba_room_id', 'digital_samba_room_url',
            'scheduled_start', 'scheduled_end', 'actual_start', 
            'actual_end', 'extended_end', 'status', 'session_notes',
            'tutor_joined', 'client_joined', 'tutor_joined_at', 'client_joined_at',
            'created_by', 'created_at', 'updated_at',
            'digital_samba_url', 'meeting_url', 'tutor_meeting_url', 'client_meeting_url',
            'duration_minutes', 'is_ongoing', 'time_remaining_minutes', 
            'gig_info', 'tutor_info', 'created_by_name'
        ]
        read_only_fields = [
            'id', 'meeting_code', 'pin_code', 'room_name', 'actual_start',
            'actual_end', 'tutor_joined', 'client_joined', 'tutor_joined_at',
            'client_joined_at', 'created_at', 'updated_at'
        ]
    
    def get_gig_info(self, obj):
        """Get basic gig information."""
        return {
            'gig_id': obj.gig.gig_id,
            'title': obj.gig.title,
            'subject_name': obj.gig.subject_name,
            'client_name': obj.gig.client_name,
            'client_email': obj.gig.client_email,
            'client_phone': obj.gig.client_phone,
        }
    
    def get_tutor_info(self, obj):
        """Get basic tutor information."""
        return {
            'tutor_id': obj.tutor.tutor_id,
            'full_name': obj.tutor.full_name,
            'email_address': obj.tutor.email_address,
            'phone_number': obj.tutor.phone_number,
        }
    
    def get_created_by_name(self, obj):
        """Get name of admin who created the session."""
        return obj.created_by.get_full_name() if obj.created_by else None


class OnlineSessionCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating online sessions.
    Tutor is automatically set from the selected gig.
    """
    tutor = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        from .models import OnlineSession
        model = OnlineSession
        fields = [
            'gig', 'tutor', 'scheduled_start', 'scheduled_end', 'session_notes'
        ]
    
    def validate(self, attrs):
        """Validate online session creation."""
        scheduled_start = attrs.get('scheduled_start')
        scheduled_end = attrs.get('scheduled_end')
        gig = attrs.get('gig')
        
        # Validate start is before end
        if scheduled_start >= scheduled_end:
            raise serializers.ValidationError({
                'scheduled_end': 'End time must be after start time.'
            })
        
        # Ensure gig has an assigned tutor
        if gig and not gig.tutor:
            raise serializers.ValidationError({
                'gig': 'Selected gig must have an assigned tutor.'
            })
        
        # Auto-assign tutor from gig
        if gig and gig.tutor:
            attrs['tutor'] = gig.tutor
        
        # Check for tutor conflicts
        from django.utils import timezone
        from .models import OnlineSession
        
        tutor = attrs.get('tutor')
        if tutor:
            conflicting_sessions = OnlineSession.objects.filter(
                tutor=tutor,
                status__in=['scheduled', 'active'],
                scheduled_start__lt=scheduled_end,
                scheduled_end__gt=scheduled_start
            )
            
            if conflicting_sessions.exists():
                raise serializers.ValidationError({
                    'scheduled_start': f'Tutor {tutor.full_name} already has a session scheduled during this time.'
                })
        
        return attrs


class OnlineSessionUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating online sessions.
    """
    class Meta:
        from .models import OnlineSession
        model = OnlineSession
        fields = ['scheduled_start', 'scheduled_end', 'session_notes', 'status']
    
    def validate(self, attrs):
        """Validate online session update."""
        scheduled_start = attrs.get('scheduled_start', self.instance.scheduled_start)
        scheduled_end = attrs.get('scheduled_end', self.instance.scheduled_end)
        
        # Validate start is before end
        if scheduled_start >= scheduled_end:
            raise serializers.ValidationError({
                'scheduled_end': 'End time must be after start time.'
            })
        
        return attrs


class OnlineSessionJoinSerializer(serializers.Serializer):
    """
    Serializer for joining an online session.
    """
    meeting_code = serializers.CharField(max_length=15)
    pin_code = serializers.CharField(max_length=6)
    participant_type = serializers.ChoiceField(choices=['tutor', 'client'])
    
    def validate(self, attrs):
        """Validate meeting code and PIN."""
        from .models import OnlineSession
        
        meeting_code = attrs.get('meeting_code')
        pin_code = attrs.get('pin_code')
        
        try:
            session = OnlineSession.objects.get(meeting_code=meeting_code)
        except OnlineSession.DoesNotExist:
            raise serializers.ValidationError({
                'meeting_code': 'Invalid meeting code.'
            })
        
        if session.pin_code != pin_code:
            raise serializers.ValidationError({
                'pin_code': 'Invalid PIN code.'
            })
        
        if session.status == 'cancelled':
            raise serializers.ValidationError({
                'meeting_code': 'This session has been cancelled.'
            })
        
        if session.status == 'completed':
            raise serializers.ValidationError({
                'meeting_code': 'This session has already ended.'
            })
        
        attrs['session'] = session
        return attrs


class OnlineSessionExtendSerializer(serializers.Serializer):
    """
    Serializer for extending an online session.
    """
    additional_minutes = serializers.IntegerField(min_value=5, max_value=120)
    
    def validate_additional_minutes(self, value):
        """Validate extension duration."""
        if value % 5 != 0:
            raise serializers.ValidationError('Extension must be in 5-minute increments.')
        return value


class OnlineMeetingRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for viewing online meeting requests.
    """
    request_id = serializers.CharField(read_only=True)
    tutor_name = serializers.CharField(source='tutor.full_name', read_only=True)
    tutor_id = serializers.CharField(source='tutor.tutor_id', read_only=True)
    gig_title = serializers.CharField(source='gig.title', read_only=True)
    gig_id = serializers.CharField(source='gig.gig_id', read_only=True)
    client_name = serializers.CharField(source='gig.client_name', read_only=True)
    subject_name = serializers.CharField(source='gig.subject_name', read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()
    requested_end = serializers.DateTimeField(read_only=True)
    created_session_id = serializers.SerializerMethodField()
    
    class Meta:
        model = OnlineMeetingRequest
        fields = [
            'id',
            'request_id',
            'gig',
            'gig_id',
            'gig_title',
            'subject_name',
            'client_name',
            'tutor',
            'tutor_id',
            'tutor_name',
            'requested_start',
            'requested_end',
            'requested_duration',
            'request_notes',
            'status',
            'reviewed_by',
            'reviewed_by_name',
            'reviewed_at',
            'admin_notes',
            'created_session',
            'created_session_id',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'request_id', 'status', 'reviewed_by', 'reviewed_by_name',
            'reviewed_at', 'created_session', 'created_session_id', 'created_at', 'updated_at'
        ]
    
    def get_reviewed_by_name(self, obj):
        """Get name of admin who reviewed."""
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None
    
    def get_created_session_id(self, obj):
        """Get the session ID if created."""
        if obj.created_session:
            return obj.created_session.session_id
        return None


class OnlineMeetingRequestCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating online meeting requests by tutors.
    """
    tutor = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = OnlineMeetingRequest
        fields = [
            'gig',
            'tutor',
            'requested_start',
            'requested_duration',
            'request_notes',
        ]
        read_only_fields = ['tutor']
    
    def validate_gig(self, value):
        """Validate the gig."""
        if value.status != 'active':
            raise serializers.ValidationError('Can only request meetings for active gigs.')
        return value
    
    def validate_requested_start(self, value):
        """Validate requested start time."""
        if value < timezone.now():
            raise serializers.ValidationError('Requested start time cannot be in the past.')
        return value
    
    def validate(self, attrs):
        """Additional validation."""
        # Ensure tutor is assigned to the gig
        request = self.context.get('request')
        if request and hasattr(request.user, 'tutor_profile'):
            tutor = request.user.tutor_profile.tutor
            gig = attrs.get('gig')
            
            if gig and gig.tutor != tutor:
                raise serializers.ValidationError({
                    'gig': 'You can only request meetings for your own gigs.'
                })
            
            attrs['tutor'] = tutor
        
        return attrs


class OnlineMeetingRequestReviewSerializer(serializers.Serializer):
    """
    Serializer for approving/rejecting meeting requests.
    """
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    admin_notes = serializers.CharField(required=False, allow_blank=True)
