# users/utils.py

from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)


def send_account_setup_email(token_obj, frontend_base_url=None):
    """
    Send account setup email to a tutor.
    
    Args:
        token_obj: AccountSetupToken instance
        frontend_base_url: Base URL of the frontend (optional)
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        # Use default frontend URL if not provided
        if not frontend_base_url:
            frontend_base_url = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:5173')
        
        # Construct the setup link
        setup_url = f"{frontend_base_url}/setup-account?token={token_obj.token}"
        
        # Email context
        context = {
            'first_name': token_obj.first_name,
            'last_name': token_obj.last_name,
            'email': token_obj.email,
            'tutor_id': token_obj.tutor_id,
            'setup_url': setup_url,
            'expires_at': token_obj.expires_at,
            'company_name': getattr(settings, 'COMPANY_NAME', 'Quest4Knowledge'),
        }
        
        # Create email content
        subject = f"Welcome to {context['company_name']} - Complete Your Account Setup"
        
        # HTML email template (you can create this template later)
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Account Setup</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; }}
                .header {{ background-color: #007bff; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ padding: 20px; }}
                .button {{ display: inline-block; background-color: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; margin: 20px 0; }}
                .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to {context['company_name']}</h1>
                </div>
                <div class="content">
                    <h2>Hello {context['first_name']} {context['last_name']},</h2>
                    <p>You've been added to the {context['company_name']} tutor platform with Tutor ID: <strong>{context['tutor_id']}</strong></p>
                    <p>To complete your account setup, please click the button below:</p>
                    
                    <a href="{setup_url}" class="button">Complete Account Setup</a>
                    
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; background-color: #f8f9fa; padding: 10px; border-radius: 4px;">{setup_url}</p>
                    
                    <p><strong>Important:</strong> This link will expire on {context['expires_at'].strftime('%B %d, %Y at %I:%M %p')}.</p>
                    
                    <p>During the setup process, you'll be able to:</p>
                    <ul>
                        <li>Set your secure password</li>
                        <li>Add your contact information</li>
                        <li>Complete your tutor profile</li>
                    </ul>
                    
                    <p>If you have any questions, please don't hesitate to contact our support team.</p>
                </div>
                <div class="footer">
                    <p>This email was sent to {context['email']}. If you did not expect this email, please contact our support team.</p>
                    <p>&copy; 2025 {context['company_name']}. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text version
        plain_message = f"""
        Hello {context['first_name']} {context['last_name']},

        You've been added to the {context['company_name']} tutor platform with Tutor ID: {context['tutor_id']}

        To complete your account setup, please visit the following link:

        {setup_url}

        This link will expire on {context['expires_at'].strftime('%B %d, %Y at %I:%M %p')}.

        During the setup process, you'll be able to set your secure password, add your contact information, and complete your tutor profile.

        If you have any questions, please don't hesitate to contact our support team.

        Best regards,
        The {context['company_name']} Team

        This email was sent to {context['email']}. If you did not expect this email, please contact our support team.
        """
        
        # Send email
        success = send_mail(
            subject=subject,
            message=plain_message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@quest4knowledge.com'),
            recipient_list=[token_obj.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Account setup email sent to {token_obj.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send account setup email to {token_obj.email}: {str(e)}")
        return False


def send_batch_import_summary_email(admin_email, total_count, success_count, failed_emails=None):
    """
    Send a summary email to the admin about the batch import results.
    
    Args:
        admin_email: Email of the admin who performed the import
        total_count: Total number of tutors in the batch
        success_count: Number of successful emails sent
        failed_emails: List of emails that failed (optional)
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        company_name = getattr(settings, 'COMPANY_NAME', 'Quest4Knowledge')
        
        subject = f"Batch Tutor Import Summary - {success_count}/{total_count} Successful"
        
        failed_section = ""
        if failed_emails:
            failed_list = "\n".join([f"- {email}" for email in failed_emails])
            failed_section = f"\n\nFailed to send emails to:\n{failed_list}"
        
        message = f"""
        Batch Tutor Import Summary
        
        Total tutors processed: {total_count}
        Successful emails sent: {success_count}
        Failed emails: {total_count - success_count}
        {failed_section}
        
        All successful tutors have been sent account setup emails and should complete their registration within 7 days.
        
        Best regards,
        {company_name} System
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@quest4knowledge.com'),
            recipient_list=[admin_email],
            fail_silently=False,
        )
        
        logger.info(f"Batch import summary email sent to {admin_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send batch summary email to {admin_email}: {str(e)}")
        return False