from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Sum, Count
from django.utils import timezone
from .models import Gig, GigSession


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
        'session_notes',
    )
    readonly_fields = ()
    
    def get_queryset(self, request):
        """Optimize queryset."""
        return super().get_queryset(request).select_related('gig')


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
        'created_at_display',
    )
    
    list_filter = (
        'session_date',
        'student_attendance',
        'gig__status',
        'gig__subject_name',
        'created_at',
    )
    
    search_fields = (
        'gig__title',
        'gig__tutor__first_name',
        'gig__tutor__last_name',
        'gig__client_name',
        'session_notes',
    )
    
    readonly_fields = (
        'created_at',
        'updated_at',
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
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
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
    
    def created_at_display(self, obj):
        """Display creation date."""
        return obj.created_at.strftime("%Y-%m-%d %H:%M")
    created_at_display.short_description = 'Created'
    created_at_display.admin_order_field = 'created_at'


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
    ]
    
    def get_queryset(self, request):
        """Optimize database queries."""
        queryset = super().get_queryset(request)
        return queryset.select_related('tutor').annotate(
            session_count=Count('sessions'),
            total_hours_logged=Sum('sessions__hours_logged')
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
        url = reverse('admin:tutors_tutor_change', args=[obj.tutor.pk])
        return format_html('<a href="{}">{}</a>', url, obj.tutor.full_name)
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
            'Client: ${}<br>Tutor: ${}<br>Profit: ${}',
            obj.total_client_fee,
            obj.total_tutor_remuneration,
            obj.profit_margin
        )
    financial_summary.short_description = 'Financials'
    
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
            'Client Rate: ${}/hr<br>Tutor Rate: ${}/hr',
            obj.hourly_rate_client,
            obj.hourly_rate_tutor
        )
    hourly_rates_display.short_description = 'Hourly Rates'
    
    def profit_analysis_display(self, obj):
        """Display profit analysis."""
        return format_html(
            'Profit: ${}<br>Margin: {}%',
            obj.profit_margin,
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


# Customize admin site for gigs
# To add a custom admin view (like reports), use custom admin URLs and views. See Django docs for 'AdminSite.get_urls' and custom admin views.