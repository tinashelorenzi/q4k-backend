from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def send_gig_assignment_emails(gig, assignment_notes=''):
    """
    Send email notifications when a gig is assigned to a tutor.
    Sends to both the tutor and the client.
    
    Args:
        gig: The Gig instance
        assignment_notes: Optional notes about the assignment
    
    Returns:
        dict: {
            'tutor_email_sent': bool,
            'client_email_sent': bool,
            'errors': list
        }
    """
    result = {
        'tutor_email_sent': False,
        'client_email_sent': False,
        'errors': []
    }
    
    if not gig.tutor:
        result['errors'].append('No tutor assigned to gig')
        return result
    
    # Prepare common context data
    support_email = getattr(settings, 'ADMIN_EMAIL', 'support@quest4knowledge.co.za')
    support_phone = getattr(settings, 'SUPPORT_PHONE', '+27 XX XXX XXXX')
    dashboard_url = f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')}/dashboard"
    
    # Format currency
    def format_currency(amount):
        return f"R {amount:,.2f}" if amount else "R 0.00"
    
    # Get level display
    level_display = dict(gig.LEVEL_CHOICES).get(gig.level, gig.level)
    
    # Get qualification display
    qualification_display = None
    if gig.tutor.highest_qualification:
        from tutors.models import Tutor
        qualification_display = dict(Tutor.QUALIFICATION_CHOICES).get(
            gig.tutor.highest_qualification, 
            gig.tutor.highest_qualification
        )
    
    # ===== Send Email to Tutor =====
    try:
        tutor_context = {
            'tutor_name': gig.tutor.full_name,
            'gig_id': gig.gig_id,
            'subject_name': gig.subject_name,
            'level': level_display,
            'total_hours': gig.total_hours,
            'tutor_remuneration': format_currency(gig.total_tutor_remuneration),
            'start_date': gig.start_date.strftime('%d %B %Y'),
            'end_date': gig.end_date.strftime('%d %B %Y'),
            'client_name': gig.client_name,
            'client_email': gig.client_email,
            'client_phone': gig.client_phone,
            'description': gig.description,
            'assignment_notes': assignment_notes,
            'dashboard_url': dashboard_url,
            'support_email': support_email,
            'support_phone': support_phone,
        }
        
        # Render HTML and text versions
        html_content = render_to_string('emails/tutor_gig_assignment.html', tutor_context)
        text_content = strip_tags(html_content)
        
        # Create and send email
        tutor_email = EmailMultiAlternatives(
            subject=f'New Gig Assignment: {gig.subject_name} ({gig.gig_id})',
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[gig.tutor.email_address],
        )
        tutor_email.attach_alternative(html_content, "text/html")
        tutor_email.send()
        
        result['tutor_email_sent'] = True
        logger.info(f"Assignment email sent to tutor {gig.tutor.email_address} for gig {gig.gig_id}")
        
    except Exception as e:
        error_msg = f"Failed to send email to tutor: {str(e)}"
        result['errors'].append(error_msg)
        logger.error(f"Error sending tutor email for gig {gig.gig_id}: {str(e)}")
    
    # ===== Send Email to Client =====
    try:
        client_context = {
            'client_name': gig.client_name,
            'tutor_name': gig.tutor.full_name,
            'tutor_id': gig.tutor.tutor_id,
            'tutor_email': gig.tutor.email_address,
            'tutor_phone': gig.tutor.phone_number,
            'tutor_qualification': qualification_display,
            'gig_id': gig.gig_id,
            'subject_name': gig.subject_name,
            'level': level_display,
            'total_hours': gig.total_hours,
            'total_fee': format_currency(gig.total_client_fee),
            'start_date': gig.start_date.strftime('%d %B %Y'),
            'end_date': gig.end_date.strftime('%d %B %Y'),
            'description': gig.description,
            'support_email': support_email,
            'support_phone': support_phone,
        }
        
        # Render HTML and text versions
        html_content = render_to_string('emails/client_tutor_assignment.html', client_context)
        text_content = strip_tags(html_content)
        
        # Create and send email
        client_email = EmailMultiAlternatives(
            subject=f'Tutor Assigned for {gig.subject_name} - {gig.tutor.full_name}',
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[gig.client_email],
        )
        client_email.attach_alternative(html_content, "text/html")
        client_email.send()
        
        result['client_email_sent'] = True
        logger.info(f"Assignment email sent to client {gig.client_email} for gig {gig.gig_id}")
        
    except Exception as e:
        error_msg = f"Failed to send email to client: {str(e)}"
        result['errors'].append(error_msg)
        logger.error(f"Error sending client email for gig {gig.gig_id}: {str(e)}")
    
    return result


def send_gig_reassignment_emails(gig, old_tutor_name, assignment_notes=''):
    """
    Send email notifications when a gig is reassigned to a different tutor.
    
    Args:
        gig: The Gig instance
        old_tutor_name: Name of the previous tutor
        assignment_notes: Optional notes about the reassignment
    
    Returns:
        dict: Result of email sending
    """
    # Send the standard assignment emails
    result = send_gig_assignment_emails(gig, assignment_notes)
    
    # Log the reassignment
    if result['tutor_email_sent'] or result['client_email_sent']:
        logger.info(f"Gig {gig.gig_id} reassigned from {old_tutor_name} to {gig.tutor.full_name}")
    
    return result

def send_session_verification_email(session, verification_notes=""):
    """Sends email notification to tutor when session is verified."""
    email_results = {'tutor_email_sent': False, 'errors': []}
    
    if not session.gig or not session.gig.tutor:
        logger.error(f"Cannot send verification email for Session {session.session_id}: No gig or tutor found.")
        email_results['errors'].append("No gig or tutor found for the session.")
        return email_results
    
    try:
        # Calculate session remuneration
        session_remuneration = float(session.hours_logged) * float(session.gig.hourly_rate_tutor)
        
        # Build duration display string
        duration_display = f"{session.start_time.strftime('%H:%M:%S')} - {session.end_time.strftime('%H:%M:%S')}"
        
        # Get verified by name
        verified_by_name = session.verified_by.get_full_name() if session.verified_by else 'System'
        
        # Context for email template - create a session dict with all needed fields
        session_data = {
            'id': session.id,
            'session_id': session.session_id,
            'session_date': session.session_date,
            'start_time': session.start_time,
            'end_time': session.end_time,
            'duration_display': duration_display,
            'hours_logged': session.hours_logged,
            'session_notes': session.session_notes,
            'is_verified': session.is_verified,
            'verified_by_name': verified_by_name,
            'verified_at': session.verified_at,
        }
        
        context = {
            'session': session_data,
            'gig': session.gig,
            'tutor': session.gig.tutor,
            'verification_notes': verification_notes,
            'session_remuneration': session_remuneration,
            'frontend_url': settings.FRONTEND_URL,
            'default_from_email': settings.DEFAULT_FROM_EMAIL,
            'current_year': timezone.now().year,
        }
        
        # Send email to tutor
        subject = f"Session Verified: {session.gig.subject_name} - {session.session_date}"
        
        html_content = render_to_string('emails/session_verification.html', context)
        text_content = f"""
        Dear {session.gig.tutor.full_name},

        Great news! Your tutoring session has been successfully verified and approved.

        Session Details:
        - Session ID: {session.session_id}
        - Subject: {session.gig.subject_name}
        - Client: {session.gig.client_name}
        - Date: {session.session_date}
        - Time: {duration_display}
        - Hours Logged: {session.hours_logged} hours
        - Status: ✅ Verified
        - Verified By: {verified_by_name}
        - Verified At: {session.verified_at}

        Session Notes: {session.session_notes or 'None'}

        {f'Admin Notes: {verification_notes}' if verification_notes else ''}

        Remuneration Earned: R{session_remuneration:.2f}
        This amount will be processed according to your payment schedule.

        Thank you for your excellent work! Your dedication to helping students succeed is truly appreciated.

        Please log in to your dashboard at {settings.FRONTEND_URL}/dashboard to view full details.

        Best regards,
        Quest4Knowledge Team
        """
        
        msg = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [session.gig.tutor.email_address]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        
        email_results['tutor_email_sent'] = True
        logger.info(f"Session verification email sent to {session.gig.tutor.email_address} for Session {session.session_id}")
        
    except Exception as e:
        logger.error(f"Failed to send session verification email to {session.gig.tutor.email_address} for Session {session.session_id}: {e}")
        email_results['errors'].append(f"Failed to send verification email to tutor {session.gig.tutor.full_name}.")
    
    return email_results



def send_online_session_invitations(online_session):
    """
    Send invitation emails to both tutor and client for an online session.
    
    Args:
        online_session: The OnlineSession instance
    
    Returns:
        dict: Result of email sending
    """
    email_results = {
        'tutor_email_sent': False,
        'client_email_sent': False,
        'errors': []
    }
    
    if not online_session.tutor or not online_session.gig:
        logger.error(f"Cannot send invitations for Online Session {online_session.session_id}: Missing tutor or gig.")
        email_results['errors'].append("Missing tutor or gig information.")
        return email_results
    
    # Prepare context data
    context = {
        'session': online_session,
        'gig': online_session.gig,
        'tutor': online_session.tutor,
        'frontend_url': settings.FRONTEND_URL,
        'default_from_email': settings.DEFAULT_FROM_EMAIL,
        'current_year': timezone.now().year,
    }
    
    # 1. Send email to Tutor
    try:
        tutor_subject = f"Online Session Scheduled: {online_session.gig.subject_name} - {online_session.scheduled_start.strftime('%b %d, %Y')}"
        tutor_html_content = render_to_string('emails/online_session_tutor_invitation.html', context)
        tutor_text_content = f"""
        Dear {online_session.tutor.full_name},

        An online tutoring session has been scheduled for you.

        Meeting Code: {online_session.meeting_code}
        PIN Code: {online_session.pin_code}

        Session Details:
        - Subject: {online_session.gig.subject_name}
        - Client: {online_session.gig.client_name}
        - Date & Time: {online_session.scheduled_start.strftime('%B %d, %Y at %I:%M %p')}
        - Duration: {online_session.duration_minutes} minutes
        - Session ID: {online_session.session_id}

        How to Join:
        1. Go to: {online_session.tutor_meeting_url}
        2. Enter the PIN code: {online_session.pin_code}
        3. Click "Join Session" and you'll be connected to Digital Samba automatically

        Client Contact Information:
        - Name: {online_session.gig.client_name}
        - Email: {online_session.gig.client_email}
        - Phone: {online_session.gig.client_phone}

        Please join a few minutes early to test your audio and video.

        Best regards,
        Quest4Knowledge Team
        """
        
        msg = EmailMultiAlternatives(
            tutor_subject,
            tutor_text_content,
            settings.DEFAULT_FROM_EMAIL,
            [online_session.tutor.email_address]
        )
        msg.attach_alternative(tutor_html_content, "text/html")
        msg.send()
        
        email_results['tutor_email_sent'] = True
        logger.info(f"Tutor invitation email sent to {online_session.tutor.email_address} for Online Session {online_session.session_id}")
        
    except Exception as e:
        logger.error(f"Failed to send tutor invitation email to {online_session.tutor.email_address} for Online Session {online_session.session_id}: {e}")
        email_results['errors'].append(f"Failed to send email to tutor {online_session.tutor.full_name}.")
    
    # 2. Send email to Client
    try:
        client_subject = f"Your Online Tutoring Session: {online_session.gig.subject_name} - {online_session.scheduled_start.strftime('%b %d, %Y')}"
        client_html_content = render_to_string('emails/online_session_client_invitation.html', context)
        client_text_content = f"""
        Dear {online_session.gig.client_name},

        Your online tutoring session for {online_session.gig.subject_name} has been scheduled!

        Meeting Code: {online_session.meeting_code}
        PIN Code: {online_session.pin_code}

        Session Details:
        - Subject: {online_session.gig.subject_name}
        - Tutor: {online_session.tutor.full_name}
        - Date & Time: {online_session.scheduled_start.strftime('%B %d, %Y at %I:%M %p')}
        - Duration: {online_session.duration_minutes} minutes
        - Session ID: {online_session.session_id}

        How to Join:
        1. Go to: {online_session.client_meeting_url}
        2. Enter the PIN code: {online_session.pin_code}
        3. Click "Join Session" and you'll be connected to Digital Samba automatically

        Your Tutor's Information:
        - Name: {online_session.tutor.full_name}
        - Email: {online_session.tutor.email_address}
        - Phone: {online_session.tutor.phone_number}

        Tips for a great session:
        - Test your internet connection beforehand
        - Find a quiet, well-lit space
        - Have your study materials ready
        - Join a few minutes early

        If you have any questions, please contact us at {settings.DEFAULT_FROM_EMAIL}.

        Best regards,
        Quest4Knowledge Team
        """
        
        msg = EmailMultiAlternatives(
            client_subject,
            client_text_content,
            settings.DEFAULT_FROM_EMAIL,
            [online_session.gig.client_email]
        )
        msg.attach_alternative(client_html_content, "text/html")
        msg.send()
        
        email_results['client_email_sent'] = True
        logger.info(f"Client invitation email sent to {online_session.gig.client_email} for Online Session {online_session.session_id}")
        
    except Exception as e:
        logger.error(f"Failed to send client invitation email to {online_session.gig.client_email} for Online Session {online_session.session_id}: {e}")
        email_results['errors'].append(f"Failed to send email to client {online_session.gig.client_name}.")
    
    return email_results
