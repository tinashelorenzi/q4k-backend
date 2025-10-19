from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Sum, Count
from django.utils import timezone
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import path
from .models import Gig, GigSession, OnlineSession


def format_zar_currency(amount):
    """Format amount as ZAR currency."""
    if amount is None:
        return "R0.00"
    return f"R{amount:,.2f}"


class GigSessionInline(admin.TabularInline):
    """
    Inline admin for GigSession within Gig admin.
    """
    model = GigSession
    extra = 0
    fields = (
        'session_date',
        'start_time',
        'end_time',
        'hours_logged',
        'student_attendance',
        'is_verified',
        'session_notes',
    )
    readonly_fields = ('is_verified',)
    
    def get_queryset(self, request):
        """Optimize queryset."""
        return super().get_queryset(request).select_related('gig', 'verified_by')


@admin.register(GigSession)
class GigSessionAdmin(admin.ModelAdmin):
    """
    Admin configuration for the GigSession model.
    """
    
    list_display = (
        'session_id_display',
        'gig_link',
        'session_date',
        'time_display',
        'hours_logged',
        'student_attendance_display',
        'verification_status_display',
        'verified_by_display',
        'created_at_display',
        'verification_actions',
    )
    
    list_filter = (
        'session_date',
        'student_attendance',
        'is_verified',
        'gig__status',
        'gig__subject_name',
        'created_at',
        'verified_at',
    )
    
    search_fields = (
        'gig__title',
        'gig__tutor__first_name',
        'gig__tutor__last_name',
        'gig__client_name',
        'session_notes',
        'verified_by__username',
        'verified_by__first_name',
        'verified_by__last_name',
    )
    
    readonly_fields = (
        'created_at',
        'updated_at',
        'verified_by',
        'verified_at',
        'is_verified',
        'verification_actions',
    )
    
    ordering = ('-session_date', '-start_time')
    
    list_per_page = 30
    
    fieldsets = (
        ('Session Information', {
            'fields': (
                'gig',
                'session_date',
                ('start_time', 'end_time'),
                'hours_logged',
            )
        }),
        ('Session Details', {
            'fields': (
                'student_attendance',
                'session_notes',
            )
        }),
        ('Verification', {
            'fields': (
                'is_verified',
                'verified_by',
                'verified_at',
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'verify_selected_sessions',
        'unverify_selected_sessions',
    ]
    
    def session_id_display(self, obj):
        """Display session ID."""
        return f"SES-{obj.pk:04d}" if obj.pk else "SES-XXXX"
    session_id_display.short_description = 'Session ID'
    session_id_display.admin_order_field = 'pk'
    
    def gig_link(self, obj):
        """Display gig with link."""
        url = reverse('admin:gigs_gig_change', args=[obj.gig.pk])
        return format_html('<a href="{}">{}</a>', url, obj.gig.gig_id)
    gig_link.short_description = 'Gig'
    gig_link.admin_order_field = 'gig'
    
    def time_display(self, obj):
        """Display session time range."""
        return f"{obj.start_time} - {obj.end_time}"
    time_display.short_description = 'Time'
    
    def student_attendance_display(self, obj):
        """Display attendance with icons."""
        if obj.student_attendance:
            return format_html('<span style="color: green;">✓ Present</span>')
        else:
            return format_html('<span style="color: red;">✗ Absent</span>')
    student_attendance_display.short_description = 'Attendance'
    
    def verification_status_display(self, obj):
        """Display verification status with icons."""
        if obj.is_verified:
            return format_html('<span style="color: green;">✓ Verified</span>')
        else:
            return format_html('<span style="color: orange;">⏳ Pending</span>')
    verification_status_display.short_description = 'Verification'
    verification_status_display.admin_order_field = 'is_verified'
    
    def verified_by_display(self, obj):
        """Display who verified the session."""
        if obj.verified_by:
            url = reverse('admin:users_user_change', args=[obj.verified_by.pk])
            return format_html('<a href="{}">{}</a>', url, obj.verified_by.get_full_name() or obj.verified_by.username)
        return "—"
    verified_by_display.short_description = 'Verified By'
    verified_by_display.admin_order_field = 'verified_by'
    
    def created_at_display(self, obj):
        """Display creation date."""
        return obj.created_at.strftime("%Y-%m-%d %H:%M")
    created_at_display.short_description = 'Created'
    created_at_display.admin_order_field = 'created_at'
    
    def verification_actions(self, obj):
        """Display verification action buttons."""
        if obj.is_verified:
            # Show unverify button for verified sessions
            unverify_url = reverse('admin:gigs_gigsession_unverify', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" style="background-color: #dc3545; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">Reject</a>',
                unverify_url
            )
        else:
            # Show verify button for unverified sessions
            verify_url = reverse('admin:gigs_gigsession_verify', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" style="background-color: #28a745; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">Validate</a>',
                verify_url
            )
    verification_actions.short_description = 'Actions'
    verification_actions.allow_tags = True
    
    # Custom Actions
    def verify_selected_sessions(self, request, queryset):
        """Verify selected sessions."""
        updated = 0
        for session in queryset.filter(is_verified=False):
            if session.verify(request.user):
                updated += 1
        
        self.message_user(
            request,
            f'{updated} session(s) were verified successfully.'
        )
    verify_selected_sessions.short_description = "Verify selected sessions"
    
    def unverify_selected_sessions(self, request, queryset):
        """Unverify selected sessions."""
        updated = 0
        for session in queryset.filter(is_verified=True):
            if session.unverify():
                updated += 1
        
        self.message_user(
            request,
            f'{updated} session(s) were unverified successfully.'
        )
    unverify_selected_sessions.short_description = "Unverify selected sessions"
    
    def get_urls(self):
        """Add custom URLs for verification actions."""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:session_id>/verify/',
                self.admin_site.admin_view(self.verify_session_view),
                name='gigs_gigsession_verify',
            ),
            path(
                '<int:session_id>/unverify/',
                self.admin_site.admin_view(self.unverify_session_view),
                name='gigs_gigsession_unverify',
            ),
        ]
        return custom_urls + urls
    
    def verify_session_view(self, request, session_id):
        """Custom view to verify a session."""
        session = get_object_or_404(GigSession, pk=session_id)
        
        if session.verify(request.user):
            messages.success(request, f'Session {session.session_id} has been verified successfully.')
        else:
            messages.error(request, f'Session {session.session_id} is already verified.')
        
        return HttpResponseRedirect(reverse('admin:gigs_gigsession_changelist'))
    
    def unverify_session_view(self, request, session_id):
        """Custom view to unverify a session."""
        session = get_object_or_404(GigSession, pk=session_id)
        
        if session.unverify():
            messages.success(request, f'Session {session.session_id} has been unverified successfully.')
        else:
            messages.error(request, f'Session {session.session_id} is not verified.')
        
        return HttpResponseRedirect(reverse('admin:gigs_gigsession_changelist'))


@admin.register(Gig)
class GigAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Gig model.
    """
    
    inlines = [GigSessionInline]
    
    list_display = (
        'gig_id_display',
        'title_display',
        'tutor_link',
        'subject_level_display',
        'client_name',
        'status_display',
        'progress_display',
        'financial_summary',
        'verification_summary',
        'dates_display',
    )
    
    list_filter = (
        'status',
        'level',
        'subject_name',
        'priority',
        'start_date',
        'created_at',
        'tutor__highest_qualification',
    )
    
    search_fields = (
        'title',
        'tutor__first_name',
        'tutor__last_name',
        'client_name',
        'client_email',
        'subject_name',
        'description',
    )
    
    readonly_fields = (
        'gig_id_display',
        'created_at',
        'updated_at',
        'hours_completed_display',
        'completion_percentage_display',
        'hourly_rates_display',
        'profit_analysis_display',
        'overdue_status_display',
        'session_count_display',
        'verification_summary_display',
    )
    
    ordering = ('-created_at',)
    
    list_per_page = 25
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'gig_id_display',
                'title',
                'tutor',
                ('subject_name', 'level'),
                'priority',
                'description',
            )
        }),
        ('Client Information', {
            'fields': (
                'client_name',
                'client_email',
                'client_phone',
            )
        }),
        ('Financial Details', {
            'fields': (
                ('total_tutor_remuneration', 'total_client_fee'),
                'hourly_rates_display',
                'profit_analysis_display',
            )
        }),
        ('Time Management', {
            'fields': (
                ('total_hours', 'total_hours_remaining'),
                'hours_completed_display',
                'completion_percentage_display',
            )
        }),
        ('Scheduling', {
            'fields': (
                ('start_date', 'end_date'),
                ('actual_start_date', 'actual_end_date'),
                'overdue_status_display',
            )
        }),
        ('Status & Tracking', {
            'fields': (
                'status',
                'session_count_display',
                'verification_summary_display',
                'notes',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'start_selected_gigs',
        'complete_selected_gigs',
        'put_on_hold',
        'resume_from_hold',
        'cancel_selected_gigs',
        'mark_as_high_priority',
        'verify_all_sessions',
    ]
    
    def get_queryset(self, request):
        """Optimize database queries."""
        queryset = super().get_queryset(request)
        return queryset.select_related('tutor').annotate(
            session_count=Count('sessions'),
            total_hours_logged=Sum('sessions__hours_logged'),
            verified_sessions_count=Count('sessions', filter=models.Q(sessions__is_verified=True)),
        )
    
    def gig_id_display(self, obj):
        """Display formatted gig ID."""
        return obj.gig_id
    gig_id_display.short_description = 'Gig ID'
    gig_id_display.admin_order_field = 'pk'
    
    def title_display(self, obj):
        """Display title with edit link."""
        url = reverse('admin:gigs_gig_change', args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.title)
    title_display.short_description = 'Title'
    title_display.admin_order_field = 'title'
    
    def tutor_link(self, obj):
        """Display tutor with link to tutor admin."""
        if obj.tutor:
            url = reverse('admin:tutors_tutor_change', args=[obj.tutor.pk])
            return format_html('<a href="{}">{}</a>', url, obj.tutor.full_name)
        return format_html('<span style="color: red;">Unassigned</span>')
    tutor_link.short_description = 'Tutor'
    tutor_link.admin_order_field = 'tutor__last_name'
    
    def subject_level_display(self, obj):
        """Display subject and level."""
        return f"{obj.subject_name} ({obj.get_level_display()})"
    subject_level_display.short_description = 'Subject & Level'
    
    def status_display(self, obj):
        """Display status with color coding."""
        status_colors = {
            'pending': 'orange',
            'active': 'green',
            'on_hold': 'blue',
            'completed': 'gray',
            'cancelled': 'red',
            'expired': 'darkred',
        }
        
        color = status_colors.get(obj.status, 'black')
        icon_map = {
            'pending': '⏳',
            'active': '▶️',
            'on_hold': '⏸️',
            'completed': '✅',
            'cancelled': '❌',
            'expired': '🔴',
        }
        
        icon = icon_map.get(obj.status, '❓')
        
        return format_html(
            '<span style="color: {};">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def progress_display(self, obj):
        """Display progress bar."""
        percentage = obj.completion_percentage
        color = 'green' if percentage >= 80 else 'orange' if percentage >= 50 else 'red'
        
        return format_html(
            '<div style="width: 100px; background-color: #f0f0f0; border: 1px solid #ccc;">'
            '<div style="width: {}%; background-color: {}; height: 20px; text-align: center; color: white; font-size: 12px;">'
            '{}%</div></div>',
            percentage, color, percentage
        )
    progress_display.short_description = 'Progress'
    
    def financial_summary(self, obj):
        """Display financial summary."""
        return format_html(
            'Client: {}<br>Tutor: {}<br>Profit: {}',
            format_zar_currency(obj.total_client_fee),
            format_zar_currency(obj.total_tutor_remuneration),
            format_zar_currency(obj.profit_margin)
        )
    financial_summary.short_description = 'Financials'
    
    def verification_summary(self, obj):
        """Display verification summary."""
        total_sessions = getattr(obj, 'session_count', obj.sessions.count())
        verified_sessions = getattr(obj, 'verified_sessions_count', 
                                   obj.sessions.filter(is_verified=True).count())
        
        if total_sessions == 0:
            return "No sessions"
        
        verification_percentage = (verified_sessions / total_sessions) * 100
        color = 'green' if verification_percentage == 100 else 'orange' if verification_percentage >= 50 else 'red'
        
        return format_html(
            '<span style="color: {};">{}/{} verified ({}%)</span>',
            color, verified_sessions, total_sessions, round(verification_percentage)
        )
    verification_summary.short_description = 'Verification'
    
    def verification_summary_display(self, obj):
        """Display detailed verification summary."""
        total_sessions = obj.sessions.count()
        verified_sessions = obj.sessions.filter(is_verified=True).count()
        pending_sessions = total_sessions - verified_sessions
        
        return format_html(
            'Total Sessions: {}<br>Verified: {}<br>Pending: {}',
            total_sessions, verified_sessions, pending_sessions
        )
    verification_summary_display.short_description = 'Verification Summary'
    
    def dates_display(self, obj):
        """Display important dates."""
        overdue = " (OVERDUE)" if obj.is_overdue else ""
        return format_html(
            'Start: {}<br>End: {}{}',
            obj.start_date,
            obj.end_date,
            f'<span style="color: red;">{overdue}</span>' if overdue else ''
        )
    dates_display.short_description = 'Dates'
    
    def hours_completed_display(self, obj):
        """Display hours completed."""
        return f"{obj.hours_completed} of {obj.total_hours} hours"
    hours_completed_display.short_description = 'Hours Completed'
    
    def completion_percentage_display(self, obj):
        """Display completion percentage."""
        return f"{obj.completion_percentage}%"
    completion_percentage_display.short_description = 'Completion %'
    
    def hourly_rates_display(self, obj):
        """Display hourly rates."""
        return format_html(
            'Client Rate: {}/hr<br>Tutor Rate: {}/hr',
            format_zar_currency(obj.hourly_rate_client),
            format_zar_currency(obj.hourly_rate_tutor)
        )
    hourly_rates_display.short_description = 'Hourly Rates'
    
    def profit_analysis_display(self, obj):
        """Display profit analysis."""
        return format_html(
            'Profit: {}<br>Margin: {}%',
            format_zar_currency(obj.profit_margin),
            obj.profit_percentage
        )
    profit_analysis_display.short_description = 'Profit Analysis'
    
    def overdue_status_display(self, obj):
        """Display overdue status."""
        if obj.is_overdue:
            return format_html('<span style="color: red; font-weight: bold;">OVERDUE</span>')
        elif obj.days_remaining is not None:
            if obj.days_remaining <= 7:
                return format_html('<span style="color: orange;">{} days remaining</span>', obj.days_remaining)
            else:
                return format_html('<span style="color: green;">{} days remaining</span>', obj.days_remaining)
        return "N/A"
    overdue_status_display.short_description = 'Due Status'
    
    def session_count_display(self, obj):
        """Display session count."""
        count = getattr(obj, 'session_count', obj.sessions.count())
        url = reverse('admin:gigs_gigsession_changelist') + f'?gig__id__exact={obj.pk}'
        return format_html('<a href="{}">{} sessions</a>', url, count)
    session_count_display.short_description = 'Sessions'
    
    # Custom Actions
    def start_selected_gigs(self, request, queryset):
        """Start selected gigs."""
        updated = 0
        for gig in queryset.filter(status='pending'):
            gig.start_gig()
            updated += 1
        
        self.message_user(
            request,
            f'{updated} gig(s) were successfully started.'
        )
    start_selected_gigs.short_description = "Start selected gigs"
    
    def complete_selected_gigs(self, request, queryset):
        """Complete selected gigs."""
        updated = 0
        for gig in queryset.filter(status='active'):
            gig.complete_gig()
            updated += 1
        
        self.message_user(
            request,
            f'{updated} gig(s) were successfully completed.'
        )
    complete_selected_gigs.short_description = "Complete selected gigs"
    
    def put_on_hold(self, request, queryset):
        """Put selected gigs on hold."""
        updated = 0
        for gig in queryset.filter(status='active'):
            gig.put_on_hold("Put on hold via admin action")
            updated += 1
        
        self.message_user(
            request,
            f'{updated} gig(s) were put on hold.'
        )
    put_on_hold.short_description = "Put selected gigs on hold"
    
    def resume_from_hold(self, request, queryset):
        """Resume selected gigs from hold."""
        updated = 0
        for gig in queryset.filter(status='on_hold'):
            gig.resume_gig()
            updated += 1
        
        self.message_user(
            request,
            f'{updated} gig(s) were resumed from hold.'
        )
    resume_from_hold.short_description = "Resume selected gigs from hold"
    
    def cancel_selected_gigs(self, request, queryset):
        """Cancel selected gigs."""
        updated = 0
        for gig in queryset.exclude(status__in=['completed', 'cancelled']):
            gig.cancel_gig("Cancelled via admin action")
            updated += 1
        
        self.message_user(
            request,
            f'{updated} gig(s) were cancelled.'
        )
    cancel_selected_gigs.short_description = "Cancel selected gigs"
    
    def mark_as_high_priority(self, request, queryset):
        """Mark selected gigs as high priority."""
        updated = queryset.update(priority='high')
        
        self.message_user(
            request,
            f'{updated} gig(s) were marked as high priority.'
        )
    mark_as_high_priority.short_description = "Mark as high priority"
    
    def verify_all_sessions(self, request, queryset):
        """Verify all sessions for selected gigs."""
        total_verified = 0
        for gig in queryset:
            for session in gig.sessions.filter(is_verified=False):
                if session.verify(request.user):
                    total_verified += 1
        
        self.message_user(
            request,
            f'{total_verified} session(s) were verified across {queryset.count()} gig(s).'
        )
    verify_all_sessions.short_description = "Verify all sessions for selected gigs"


# Need to import models for the queryset annotation
from django.db import models


@admin.register(OnlineSession)
class OnlineSessionAdmin(admin.ModelAdmin):
    """
    Admin configuration for the OnlineSession model.
    """
    
    list_display = (
        'session_id_display',
        'gig_link',
        'tutor_link',
        'meeting_code',
        'scheduled_start',
        'duration_display',
        'status_display',
        'participants_display',
    )
    
    list_filter = (
        'status',
        'scheduled_start',
        'tutor',
        'tutor_joined',
        'client_joined',
    )
    
    search_fields = (
        'meeting_code',
        'pin_code',
        'gig__title',
        'gig__subject_name',
        'tutor__first_name',
        'tutor__last_name',
        'gig__client_name',
    )
    
    readonly_fields = (
        'meeting_code',
        'pin_code',
        'room_name',
        'actual_start',
        'actual_end',
        'tutor_joined',
        'client_joined',
        'tutor_joined_at',
        'client_joined_at',
        'created_at',
        'updated_at',
        'jitsi_url_display',
        'meeting_url_display',
    )
    
    fieldsets = (
        ('Session Information', {
            'fields': (
                ('gig', 'tutor'),
                ('scheduled_start', 'scheduled_end'),
                'extended_end',
                'session_notes',
            )
        }),
        ('Meeting Access', {
            'fields': (
                'meeting_code',
                'pin_code',
                'room_name',
                'jitsi_url_display',
                'meeting_url_display',
            ),
            'classes': ('collapse',)
        }),
        ('Session Status', {
            'fields': (
                'status',
                ('actual_start', 'actual_end'),
            )
        }),
        ('Participant Tracking', {
            'fields': (
                ('tutor_joined', 'tutor_joined_at'),
                ('client_joined', 'client_joined_at'),
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'created_by',
            ),
            'classes': ('collapse',)
        }),
    )
    
    def session_id_display(self, obj):
        """Display session ID."""
        return obj.session_id
    session_id_display.short_description = 'Session ID'
    
    def gig_link(self, obj):
        """Display gig with link."""
        url = reverse('admin:gigs_gig_change', args=[obj.gig.pk])
        return format_html('<a href="{}">{}</a>', url, obj.gig.gig_id)
    gig_link.short_description = 'Gig'
    
    def tutor_link(self, obj):
        """Display tutor with link."""
        if obj.tutor:
            url = reverse('admin:tutors_tutor_change', args=[obj.tutor.pk])
            return format_html('<a href="{}">{}</a>', url, obj.tutor.full_name)
        return "—"
    tutor_link.short_description = 'Tutor'
    
    def duration_display(self, obj):
        """Display session duration."""
        return f"{obj.duration_minutes} min"
    duration_display.short_description = 'Duration'
    
    def status_display(self, obj):
        """Display status with color coding."""
        status_colors = {
            'scheduled': 'blue',
            'active': 'green',
            'completed': 'gray',
            'cancelled': 'red',
        }
        color = status_colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def participants_display(self, obj):
        """Display participant join status."""
        tutor_status = '✓' if obj.tutor_joined else '✗'
        client_status = '✓' if obj.client_joined else '✗'
        return format_html(
            'Tutor: {} | Client: {}',
            tutor_status, client_status
        )
    participants_display.short_description = 'Participants'
    
    def jitsi_url_display(self, obj):
        """Display clickable Jitsi URL."""
        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            obj.jitsi_url, obj.jitsi_url
        )
    jitsi_url_display.short_description = 'Jitsi URL'
    
    def meeting_url_display(self, obj):
        """Display clickable meeting URL."""
        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            obj.meeting_url, obj.meeting_url
        )
    meeting_url_display.short_description = 'Meeting URL'


# Customize admin site for gigs
admin.site.site_header = "Quest4Knowledge Gig Management (ZAR)"
admin.site.site_title = "Q4K Admin"
admin.site.index_title = "Welcome to Quest4Knowledge Gig Administration"