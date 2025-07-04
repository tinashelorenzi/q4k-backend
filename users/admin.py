from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count
from .models import User, TutorProfile, UserSession


class TutorProfileInline(admin.StackedInline):
    """
    Inline admin for TutorProfile within User admin.
    """
    model = TutorProfile
    extra = 0
    fields = (
        'tutor',
        'bio',
        'subjects_of_expertise',
        'years_of_experience',
        'hourly_rate',
        'is_available',
    )
    readonly_fields = ('created_at', 'updated_at')


class UserSessionInline(admin.TabularInline):
    """
    Inline admin for UserSession within User admin.
    """
    model = UserSession
    extra = 0
    fields = (
        'session_key',
        'ip_address',
        'user_agent',
        'is_active',
        'last_activity',
    )
    readonly_fields = ('session_key', 'ip_address', 'user_agent', 'created_at', 'last_activity')
    
    def get_queryset(self, request):
        """Optimize queryset."""
        return super().get_queryset(request).select_related('user')


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """
    Admin configuration for the UserSession model.
    """
    
    list_display = (
        'session_id_display',
        'user_link',
        'ip_address',
        'is_active_display',
        'last_activity_display',
        'created_at_display',
    )
    
    list_filter = (
        'is_active',
        'created_at',
        'last_activity',
        'user__user_type',
    )
    
    search_fields = (
        'user__username',
        'user__email',
        'user__first_name',
        'user__last_name',
        'ip_address',
        'session_key',
    )
    
    readonly_fields = (
        'session_key',
        'ip_address',
        'user_agent',
        'created_at',
        'last_activity',
    )
    
    ordering = ('-last_activity',)
    
    list_per_page = 50
    
    fieldsets = (
        ('Session Information', {
            'fields': (
                'user',
                'session_key',
                'ip_address',
                'user_agent',
            )
        }),
        ('Status', {
            'fields': (
                'is_active',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'last_activity',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'deactivate_selected_sessions',
        'activate_selected_sessions',
    ]
    
    def session_id_display(self, obj):
        """Display session ID."""
        return f"SES-{obj.pk:06d}" if obj.pk else "SES-XXXXXX"
    session_id_display.short_description = 'Session ID'
    session_id_display.admin_order_field = 'pk'
    
    def user_link(self, obj):
        """Display user with link."""
        url = reverse('admin:users_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__username'
    
    def is_active_display(self, obj):
        """Display active status with icons."""
        if obj.is_active:
            return format_html('<span style="color: green;">✓ Active</span>')
        else:
            return format_html('<span style="color: red;">✗ Inactive</span>')
    is_active_display.short_description = 'Status'
    
    def last_activity_display(self, obj):
        """Display last activity."""
        return obj.last_activity.strftime("%Y-%m-%d %H:%M")
    last_activity_display.short_description = 'Last Activity'
    last_activity_display.admin_order_field = 'last_activity'
    
    def created_at_display(self, obj):
        """Display creation date."""
        return obj.created_at.strftime("%Y-%m-%d %H:%M")
    created_at_display.short_description = 'Created'
    created_at_display.admin_order_field = 'created_at'
    
    # Custom Actions
    def deactivate_selected_sessions(self, request, queryset):
        """Deactivate selected sessions."""
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f'{updated} session(s) were deactivated.'
        )
    deactivate_selected_sessions.short_description = "Deactivate selected sessions"
    
    def activate_selected_sessions(self, request, queryset):
        """Activate selected sessions."""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f'{updated} session(s) were activated.'
        )
    activate_selected_sessions.short_description = "Activate selected sessions"


@admin.register(TutorProfile)
class TutorProfileAdmin(admin.ModelAdmin):
    """
    Admin configuration for the TutorProfile model.
    """
    
    list_display = (
        'profile_id_display',
        'user_link',
        'tutor_link',
        'years_of_experience',
        'hourly_rate_display',
        'is_available_display',
        'created_at_display',
    )
    
    list_filter = (
        'is_available',
        'years_of_experience',
        'created_at',
        'user__user_type',
    )
    
    search_fields = (
        'user__username',
        'user__email',
        'user__first_name',
        'user__last_name',
        'tutor__first_name',
        'tutor__last_name',
        'bio',
        'subjects_of_expertise',
    )
    
    readonly_fields = (
        'created_at',
        'updated_at',
    )
    
    ordering = ('-created_at',)
    
    list_per_page = 25
    
    fieldsets = (
        ('User Information', {
            'fields': (
                'user',
                'tutor',
            )
        }),
        ('Profile Details', {
            'fields': (
                'bio',
                'subjects_of_expertise',
                'years_of_experience',
                'hourly_rate',
            )
        }),
        ('Status', {
            'fields': (
                'is_available',
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
        'make_available',
        'make_unavailable',
    ]
    
    def profile_id_display(self, obj):
        """Display profile ID."""
        return f"PROF-{obj.pk:04d}" if obj.pk else "PROF-XXXX"
    profile_id_display.short_description = 'Profile ID'
    profile_id_display.admin_order_field = 'pk'
    
    def user_link(self, obj):
        """Display user with link."""
        url = reverse('admin:users_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__username'
    
    def tutor_link(self, obj):
        """Display tutor with link."""
        if obj.tutor:
            url = reverse('admin:tutors_tutor_change', args=[obj.tutor.pk])
            return format_html('<a href="{}">{}</a>', url, obj.tutor.full_name)
        return "Not linked"
    tutor_link.short_description = 'Tutor'
    
    def hourly_rate_display(self, obj):
        """Display hourly rate."""
        if obj.hourly_rate:
            return f"${obj.hourly_rate}/hr"
        return "Not set"
    hourly_rate_display.short_description = 'Hourly Rate'
    
    def is_available_display(self, obj):
        """Display availability status."""
        if obj.is_available:
            return format_html('<span style="color: green;">✓ Available</span>')
        else:
            return format_html('<span style="color: red;">✗ Unavailable</span>')
    is_available_display.short_description = 'Available'
    
    def created_at_display(self, obj):
        """Display creation date."""
        return obj.created_at.strftime("%Y-%m-%d %H:%M")
    created_at_display.short_description = 'Created'
    created_at_display.admin_order_field = 'created_at'
    
    # Custom Actions
    def make_available(self, request, queryset):
        """Make selected profiles available."""
        updated = queryset.update(is_available=True)
        self.message_user(
            request,
            f'{updated} profile(s) were marked as available.'
        )
    make_available.short_description = "Make selected profiles available"
    
    def make_unavailable(self, request, queryset):
        """Make selected profiles unavailable."""
        updated = queryset.update(is_available=False)
        self.message_user(
            request,
            f'{updated} profile(s) were marked as unavailable.'
        )
    make_unavailable.short_description = "Make selected profiles unavailable"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin configuration for the custom User model.
    """
    
    inlines = [TutorProfileInline, UserSessionInline]
    
    list_display = (
        'user_id_display',
        'username_display',
        'full_name_display',
        'email_display',
        'user_type_display',
        'status_display',
        'login_status_display',
        'created_at_display',
    )
    
    list_filter = (
        'user_type',
        'is_active',
        'is_verified',
        'is_approved',
        'is_staff',
        'is_superuser',
        'created_at',
        'last_login',
    )
    
    search_fields = (
        'username',
        'email',
        'first_name',
        'last_name',
        'phone_number',
    )
    
    readonly_fields = (
        'user_id_display',
        'created_at',
        'updated_at',
        'last_login_ip',
        'failed_login_attempts',
        'locked_until',
        'account_status_display',
        'session_count_display',
        'login_status_display',
    )
    
    ordering = ('-created_at',)
    
    list_per_page = 25
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'user_id_display',
                'username',
                ('first_name', 'last_name'),
                'email',
                'phone_number',
                'profile_picture',
            )
        }),
        ('Account Type & Permissions', {
            'fields': (
                'user_type',
                ('is_active', 'is_staff', 'is_superuser'),
                'groups',
                'user_permissions',
            )
        }),
        ('Verification & Approval', {
            'fields': (
                ('is_verified', 'is_approved'),
                'account_status_display',
            )
        }),
        ('Security & Login', {
            'fields': (
                'last_login_ip',
                'failed_login_attempts',
                'locked_until',
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'last_login',
                'session_count_display',
            ),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        ('Basic Information', {
            'fields': (
                'username',
                ('first_name', 'last_name'),
                'email',
                'phone_number',
                'user_type',
            )
        }),
        ('Security', {
            'fields': (
                'password1',
                'password2',
            )
        }),
        ('Permissions', {
            'fields': (
                ('is_active', 'is_staff', 'is_superuser'),
                'groups',
                'user_permissions',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'verify_selected_users',
        'approve_selected_users',
        'unverify_selected_users',
        'unapprove_selected_users',
        'activate_selected_users',
        'deactivate_selected_users',
        'unlock_selected_accounts',
        'reset_failed_login_attempts',
    ]
    
    def get_queryset(self, request):
        """Optimize database queries."""
        queryset = super().get_queryset(request)
        return queryset.annotate(
            session_count=Count('sessions')
        )
    
    def user_id_display(self, obj):
        """Display formatted user ID."""
        return f"USR-{obj.pk:04d}" if obj.pk else "USR-XXXX"
    user_id_display.short_description = 'User ID'
    user_id_display.admin_order_field = 'pk'
    
    def username_display(self, obj):
        """Display username with edit link."""
        url = reverse('admin:users_user_change', args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.username)
    username_display.short_description = 'Username'
    username_display.admin_order_field = 'username'
    
    def full_name_display(self, obj):
        """Display full name."""
        return obj.get_full_name() or "No name provided"
    full_name_display.short_description = 'Full Name'
    full_name_display.admin_order_field = 'last_name'
    
    def email_display(self, obj):
        """Display email."""
        return obj.email
    email_display.short_description = 'Email'
    email_display.admin_order_field = 'email'
    
    def user_type_display(self, obj):
        """Display user type with color coding."""
        type_colors = {
            'admin': 'red',
            'manager': 'blue',
            'tutor': 'green',
            'staff': 'orange',
        }
        color = type_colors.get(obj.user_type, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color, obj.get_user_type_display()
        )
    user_type_display.short_description = 'User Type'
    user_type_display.admin_order_field = 'user_type'
    
    def status_display(self, obj):
        """Display account status."""
        status_parts = []
        
        if obj.is_active:
            status_parts.append(format_html('<span style="color: green;">✓ Active</span>'))
        else:
            status_parts.append(format_html('<span style="color: red;">✗ Inactive</span>'))
        
        if obj.is_verified:
            status_parts.append(format_html('<span style="color: green;">✓ Verified</span>'))
        else:
            status_parts.append(format_html('<span style="color: orange;">⚠ Unverified</span>'))
        
        if obj.is_approved:
            status_parts.append(format_html('<span style="color: green;">✓ Approved</span>'))
        else:
            status_parts.append(format_html('<span style="color: orange;">⚠ Pending</span>'))
        
        return format_html('<br>'.join(status_parts))
    status_display.short_description = 'Status'
    
    def login_status_display(self, obj):
        """Display login status."""
        if obj.is_account_locked:
            return format_html('<span style="color: red;">🔒 Locked</span>')
        elif obj.failed_login_attempts > 0:
            return format_html('<span style="color: orange;">⚠ {} failed attempts</span>', obj.failed_login_attempts)
        else:
            return format_html('<span style="color: green;">✓ OK</span>')
    login_status_display.short_description = 'Login Status'
    
    def created_at_display(self, obj):
        """Display creation date."""
        return obj.created_at.strftime("%Y-%m-%d %H:%M")
    created_at_display.short_description = 'Created'
    created_at_display.admin_order_field = 'created_at'
    
    def account_status_display(self, obj):
        """Display comprehensive account status."""
        status_parts = []
        
        if obj.can_login:
            status_parts.append(format_html('<span style="color: green;">✓ Can Login</span>'))
        else:
            reasons = []
            if not obj.is_active:
                reasons.append("Account inactive")
            if not obj.is_verified:
                reasons.append("Email not verified")
            if not obj.is_approved:
                reasons.append("Not approved")
            if obj.is_account_locked:
                reasons.append("Account locked")
            
            status_parts.append(format_html(
                '<span style="color: red;">✗ Cannot Login: {}</span>',
                ', '.join(reasons)
            ))
        
        return format_html('<br>'.join(status_parts))
    account_status_display.short_description = 'Account Status'
    
    def session_count_display(self, obj):
        """Display session count."""
        count = getattr(obj, 'session_count', obj.sessions.count())
        url = reverse('admin:users_usersession_changelist') + f'?user__id__exact={obj.pk}'
        return format_html('<a href="{}">{} sessions</a>', url, count)
    session_count_display.short_description = 'Sessions'
    
    # Custom Actions
    def verify_selected_users(self, request, queryset):
        """Verify selected users."""
        updated = 0
        for user in queryset:
            if not user.is_verified:
                user.verify_email()
                updated += 1
        
        self.message_user(
            request,
            f'{updated} user(s) were verified.'
        )
    verify_selected_users.short_description = "Verify selected users"
    
    def approve_selected_users(self, request, queryset):
        """Approve selected users."""
        updated = 0
        for user in queryset:
            if not user.is_approved:
                user.approve_user()
                updated += 1
        
        self.message_user(
            request,
            f'{updated} user(s) were approved.'
        )
    approve_selected_users.short_description = "Approve selected users"
    
    def unverify_selected_users(self, request, queryset):
        """Unverify selected users."""
        updated = queryset.update(is_verified=False)
        self.message_user(
            request,
            f'{updated} user(s) were unverified.'
        )
    unverify_selected_users.short_description = "Unverify selected users"
    
    def unapprove_selected_users(self, request, queryset):
        """Unapprove selected users."""
        updated = queryset.update(is_approved=False)
        self.message_user(
            request,
            f'{updated} user(s) were unapproved.'
        )
    unapprove_selected_users.short_description = "Unapprove selected users"
    
    def activate_selected_users(self, request, queryset):
        """Activate selected users."""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f'{updated} user(s) were activated.'
        )
    activate_selected_users.short_description = "Activate selected users"
    
    def deactivate_selected_users(self, request, queryset):
        """Deactivate selected users."""
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f'{updated} user(s) were deactivated.'
        )
    deactivate_selected_users.short_description = "Deactivate selected users"
    
    def unlock_selected_accounts(self, request, queryset):
        """Unlock selected accounts."""
        updated = 0
        for user in queryset:
            if user.is_account_locked:
                user.unlock_account()
                updated += 1
        
        self.message_user(
            request,
            f'{updated} account(s) were unlocked.'
        )
    unlock_selected_accounts.short_description = "Unlock selected accounts"
    
    def reset_failed_login_attempts(self, request, queryset):
        """Reset failed login attempts."""
        updated = queryset.update(failed_login_attempts=0, locked_until=None)
        self.message_user(
            request,
            f'{updated} user(s) had their failed login attempts reset.'
        )
    reset_failed_login_attempts.short_description = "Reset failed login attempts"


# Customize admin site for users
admin.site.site_header = "Quest4Knowledge User Management"
admin.site.site_title = "Q4K Admin"
admin.site.index_title = "Welcome to Quest4Knowledge Administration"
