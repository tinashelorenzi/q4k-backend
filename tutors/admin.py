from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Tutor


@admin.register(Tutor)
class TutorAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Tutor model.
    """
    
    # List display configuration
    list_display = (
        'tutor_id_display',
        'full_name_display',
        'email_address',
        'phone_number',
        'highest_qualification',
        'status_display',
        'created_at_display',
    )
    
    # List filters
    list_filter = (
        'is_active',
        'is_blocked',
        'highest_qualification',
        'created_at',
        'updated_at',
    )
    
    # Search fields
    search_fields = (
        'first_name',
        'last_name',
        'email_address',
        'phone_number',
    )
    
    # Fields that are read-only
    readonly_fields = (
        'created_at',
        'updated_at',
        'status_display',
    )
    
    # Ordering
    ordering = ('-created_at',)
    
    # Pagination
    list_per_page = 25
    
    # Fields to display in the form
    fieldsets = (
        ('Personal Information', {
            'fields': (
                'tutor_id',
                ('first_name', 'last_name'),
                'email_address',
                'phone_number',
                'physical_address',
            )
        }),
        ('Educational Background', {
            'fields': ('highest_qualification',)
        }),
        ('Status', {
            'fields': (
                ('is_active', 'is_blocked'),
                'status_display',
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
    
    # Actions
    actions = [
        'activate_tutors',
        'deactivate_tutors',
        'block_tutors',
        'unblock_tutors',
    ]
    
    def tutor_id_display(self, obj):
        """Display formatted tutor ID."""
        return obj.tutor_id_display
    tutor_id_display.short_description = 'Tutor ID'
    tutor_id_display.admin_order_field = 'tutor_id'
    
    def full_name_display(self, obj):
        """Display full name with a link to edit."""
        url = reverse('admin:tutors_tutor_change', args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.full_name)
    full_name_display.short_description = 'Full Name'
    full_name_display.admin_order_field = 'last_name'
    
    def status_display(self, obj):
        """Display status with color coding."""
        status = obj.status
        if status == 'Active':
            color = 'green'
            icon = '✓'
        elif status == 'Blocked':
            color = 'red'
            icon = '✗'
        else:  # Inactive
            color = 'orange'
            icon = '⚠'
        
        return format_html(
            '<span style="color: {};">{} {}</span>',
            color, icon, status
        )
    status_display.short_description = 'Status'
    
    def created_at_display(self, obj):
        """Display creation date in a readable format."""
        return obj.created_at.strftime("%Y-%m-%d %H:%M")
    created_at_display.short_description = 'Created'
    created_at_display.admin_order_field = 'created_at'
    
    # Custom actions
    def activate_tutors(self, request, queryset):
        """Activate selected tutors."""
        updated = 0
        for tutor in queryset:
            if not tutor.is_active and not tutor.is_blocked:
                tutor.activate()
                updated += 1
        
        self.message_user(
            request,
            f'{updated} tutor(s) were successfully activated.'
        )
    activate_tutors.short_description = "Activate selected tutors"
    
    def deactivate_tutors(self, request, queryset):
        """Deactivate selected tutors."""
        updated = 0
        for tutor in queryset:
            if tutor.is_active:
                tutor.deactivate()
                updated += 1
        
        self.message_user(
            request,
            f'{updated} tutor(s) were successfully deactivated.'
        )
    deactivate_tutors.short_description = "Deactivate selected tutors"
    
    def block_tutors(self, request, queryset):
        """Block selected tutors."""
        updated = 0
        for tutor in queryset:
            if not tutor.is_blocked:
                tutor.block()
                updated += 1
        
        self.message_user(
            request,
            f'{updated} tutor(s) were successfully blocked.'
        )
    block_tutors.short_description = "Block selected tutors"
    
    def unblock_tutors(self, request, queryset):
        """Unblock selected tutors."""
        updated = 0
        for tutor in queryset:
            if tutor.is_blocked:
                tutor.unblock()
                updated += 1
        
        self.message_user(
            request,
            f'{updated} tutor(s) were successfully unblocked.'
        )
    unblock_tutors.short_description = "Unblock selected tutors"
    
    def get_queryset(self, request):
        """Optimize database queries."""
        queryset = super().get_queryset(request)
        return queryset.select_related()
    
    def save_model(self, request, obj, form, change):
        """Override save to add custom logic if needed."""
        super().save_model(request, obj, form, change)
        
        # Log the action (you can expand this)
        action = 'updated' if change else 'created'
        self.message_user(
            request,
            f'Tutor {obj.full_name} was successfully {action}.'
        )


# Optional: Customize the admin site header and title
admin.site.site_header = "Tutor Management System"
admin.site.site_title = "TMS Admin"
admin.site.index_title = "Welcome to Tutor Management System Administration"