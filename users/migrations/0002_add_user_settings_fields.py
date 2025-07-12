# Create this file as: users/migrations/0002_add_user_settings_fields.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        # Notification Settings
        migrations.AddField(
            model_name='user',
            name='email_notifications',
            field=models.BooleanField(default=True, help_text='Whether to receive notifications via email'),
        ),
        migrations.AddField(
            model_name='user',
            name='sms_notifications',
            field=models.BooleanField(default=False, help_text='Whether to receive notifications via SMS'),
        ),
        migrations.AddField(
            model_name='user',
            name='push_notifications',
            field=models.BooleanField(default=True, help_text='Whether to receive push notifications'),
        ),
        migrations.AddField(
            model_name='user',
            name='marketing_emails',
            field=models.BooleanField(default=False, help_text='Whether to receive marketing and promotional emails'),
        ),
        
        # Preference Settings
        migrations.AddField(
            model_name='user',
            name='language_preference',
            field=models.CharField(
                choices=[('en', 'English'), ('af', 'Afrikaans'), ('zu', 'Zulu'), ('xh', 'Xhosa')], 
                default='en', 
                help_text='Preferred language for the interface', 
                max_length=10
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='timezone',
            field=models.CharField(default='Africa/Johannesburg', help_text='User timezone preference', max_length=50),
        ),
        migrations.AddField(
            model_name='user',
            name='date_format',
            field=models.CharField(
                choices=[
                    ('YYYY-MM-DD', 'YYYY-MM-DD (2024-12-31)'), 
                    ('DD/MM/YYYY', 'DD/MM/YYYY (31/12/2024)'), 
                    ('MM/DD/YYYY', 'MM/DD/YYYY (12/31/2024)'), 
                    ('DD-MM-YYYY', 'DD-MM-YYYY (31-12-2024)')
                ], 
                default='YYYY-MM-DD', 
                help_text='Preferred date display format', 
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='time_format',
            field=models.CharField(
                choices=[('24h', '24 Hour (14:30)'), ('12h', '12 Hour (2:30 PM)')], 
                default='24h', 
                help_text='Preferred time display format', 
                max_length=10
            ),
        ),
        
        # Privacy Settings
        migrations.AddField(
            model_name='user',
            name='profile_visible',
            field=models.BooleanField(default=True, help_text='Whether profile is visible to other users'),
        ),
        migrations.AddField(
            model_name='user',
            name='show_online_status',
            field=models.BooleanField(default=True, help_text='Whether to show online status to other users'),
        ),
        migrations.AddField(
            model_name='user',
            name='show_email',
            field=models.BooleanField(default=False, help_text='Whether to show email address in profile'),
        ),
        migrations.AddField(
            model_name='user',
            name='show_phone',
            field=models.BooleanField(default=False, help_text='Whether to show phone number in profile'),
        ),
        
        # Security Settings
        migrations.AddField(
            model_name='user',
            name='two_factor_enabled',
            field=models.BooleanField(default=False, help_text='Whether two-factor authentication is enabled'),
        ),
        migrations.AddField(
            model_name='user',
            name='login_notifications',
            field=models.BooleanField(default=True, help_text='Whether to receive notifications on new logins'),
        ),
        migrations.AddField(
            model_name='user',
            name='session_timeout',
            field=models.PositiveIntegerField(default=1440, help_text='Session timeout in minutes (0 = never expire)'),
        ),
        
        # Theme Settings
        migrations.AddField(
            model_name='user',
            name='theme_preference',
            field=models.CharField(
                choices=[('light', 'Light Theme'), ('dark', 'Dark Theme'), ('auto', 'Auto (System)')], 
                default='light', 
                help_text='Preferred theme for the interface', 
                max_length=10
            ),
        ),
        
        # Add indexes for frequently queried fields
        migrations.AddIndex(
            model_name='user',
            index=models.Index(fields=['language_preference'], name='users_language_pref_idx'),
        ),
        migrations.AddIndex(
            model_name='user',
            index=models.Index(fields=['theme_preference'], name='users_theme_pref_idx'),
        ),
    ]