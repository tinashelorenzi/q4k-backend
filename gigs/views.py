from rest_framework import status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q, Sum
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
from .pagination import SessionPagination
import logging

from .models import Gig, GigSession
from tutors.models import Tutor
from .serializers import (
    GigSerializer,
    GigDetailSerializer,
    GigListSerializer,
    GigCreateSerializer,
    GigUpdateSerializer,
    GigAssignmentSerializer,
    GigStatusChangeSerializer,
    GigHoursAdjustmentSerializer,
    GigSessionSerializer,
    GigSessionCreateSerializer,
    GigSessionDetailSerializer,
    SessionVerificationSerializer,
)

# Set up logging
logger = logging.getLogger(__name__)
def parse_gig_id(gig_id):
    """
    Parse gig ID and return the numeric ID.
    Handles both 'GIG-0001' and 'GIG0001' formats.
    """
    print(f"DEBUG: parse_gig_id called with: '{gig_id}'")
    
    if gig_id.startswith('GIG-'):
        # Handle GIG-0001 format
        try:
            result = int(gig_id.split('-')[1])
            print(f"DEBUG: Parsed GIG- format, result: {result}")
            return result
        except (ValueError, IndexError):
            print(f"DEBUG: Failed to parse GIG- format")
            raise ValueError('Invalid gig ID format')
    elif gig_id.startswith('GIG') and len(gig_id) > 3:
        # Handle GIG0001 format
        try:
            result = int(gig_id[3:])  # Extract everything after 'GIG'
            print(f"DEBUG: Parsed GIG format, result: {result}")
            return result
        except ValueError:
            print(f"DEBUG: Failed to parse GIG format")
            raise ValueError('Invalid gig ID format')
    else:
        # Assume it's already a numeric ID
        try:
            result = int(gig_id)
            print(f"DEBUG: Parsed numeric format, result: {result}")
            return result
        except ValueError:
            print(f"DEBUG: Failed to parse numeric format")
            raise ValueError('Invalid gig ID format')

class GigPagination(PageNumberPagination):
    """Custom pagination for gigs."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class SessionPagination(PageNumberPagination):
    """Custom pagination for sessions."""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


def get_client_ip(request):
    """Extract client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def can_access_gig(user, gig):
    """Check if user can access the gig."""
    if user.is_admin or user.is_staff:
        return True
    if user.is_tutor and gig.tutor:
        try:
            tutor_profile = user.tutor_profile
            return tutor_profile.tutor == gig.tutor
        except:
            pass
    return False


def can_modify_gig(user, gig):
    """Check if user can modify the gig."""
    if user.is_admin or user.is_staff:
        return True
    # Tutors can only modify their own gigs in certain ways
    if user.is_tutor and gig.tutor:
        try:
            tutor_profile = user.tutor_profile
            return tutor_profile.tutor == gig.tutor
        except:
            pass
    return False


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def gigs_list_create(request):
    """
    GET: List all gigs with filtering and pagination
    POST: Create a new gig (admin only)
    """
    try:
        if request.method == 'GET':
            # Get base queryset
            queryset = Gig.objects.select_related('tutor').annotate(
                sessions_count=Count('sessions')
            )
            
            # Filter by user permissions
            if not (request.user.is_admin or request.user.is_staff):
                if request.user.is_tutor:
                    try:
                        tutor_profile = request.user.tutor_profile
                        queryset = queryset.filter(tutor=tutor_profile.tutor)
                    except:
                        queryset = queryset.none()
                else:
                    queryset = queryset.none()
            
            # Apply filters
            search = request.GET.get('search', '')
            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search) |
                    Q(subject_name__icontains=search) |
                    Q(client_name__icontains=search) |
                    Q(tutor__first_name__icontains=search) |
                    Q(tutor__last_name__icontains=search)
                )
            
            # Filter by status
            status_filter = request.GET.get('status')
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            
            # Filter by tutor
            tutor_id = request.GET.get('tutor_id')
            if tutor_id:
                queryset = queryset.filter(tutor_id=tutor_id)
            
            # Filter by priority
            priority = request.GET.get('priority')
            if priority:
                queryset = queryset.filter(priority=priority)
            
            # Filter by subject
            subject = request.GET.get('subject')
            if subject:
                queryset = queryset.filter(subject_name__icontains=subject)
            
            # Filter by level
            level = request.GET.get('level')
            if level:
                queryset = queryset.filter(level=level)
            
            # Filter by overdue
            overdue = request.GET.get('overdue')
            if overdue == 'true':
                queryset = queryset.filter(
                    status='active',
                    end_date__lt=timezone.now().date()
                )
            
            # Order by
            ordering = request.GET.get('ordering', '-created_at')
            valid_orderings = [
                'created_at', '-created_at',
                'title', '-title',
                'start_date', '-start_date',
                'end_date', '-end_date',
                'priority', '-priority',
                'status', '-status',
                'sessions_count', '-sessions_count'
            ]
            if ordering in valid_orderings:
                queryset = queryset.order_by(ordering)
            
            # Paginate results
            paginator = GigPagination()
            page = paginator.paginate_queryset(queryset, request)
            
            if page is not None:
                serializer = GigListSerializer(page, many=True)
                return paginator.get_paginated_response(serializer.data)
            
            serializer = GigListSerializer(queryset, many=True)
            return Response(serializer.data)
        
        elif request.method == 'POST':
            # Check if user can create gigs
            if not (request.user.is_admin or request.user.is_staff):
                return Response({
                    'error': 'Permission denied',
                    'detail': 'Only administrators can create gigs.'
                }, status=status.HTTP_403_FORBIDDEN)
            
            serializer = GigCreateSerializer(data=request.data)
            
            if serializer.is_valid():
                gig = serializer.save()
                
                logger.info(f"New gig created by {request.user.email}: {gig.gig_id}")
                
                return Response({
                    'message': 'Gig created successfully',
                    'gig': GigDetailSerializer(gig).data
                }, status=status.HTTP_201_CREATED)
            
            return Response({
                'error': 'Validation failed',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error in gigs_list_create: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def gig_detail(request, gig_id):
    """
    GET: Retrieve a specific gig by ID
    PUT/PATCH: Update gig information
    DELETE: Delete gig (admin only)
    """
    try:
        # Get gig by ID or gig_id format
        if gig_id.startswith('GIG-'):
            try:
                numeric_id = int(gig_id.split('-')[1])
                gig = get_object_or_404(Gig, pk=numeric_id)
            except (ValueError, IndexError):
                return Response({
                    'error': 'Invalid gig ID format'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            gig = get_object_or_404(Gig, pk=gig_id)
        
        # Check permissions
        if not can_access_gig(request.user, gig):
            return Response({
                'error': 'Permission denied',
                'detail': 'You can only access your own gigs or be an administrator.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if request.method == 'GET':
            serializer = GigDetailSerializer(gig)
            return Response(serializer.data)
        
        elif request.method in ['PUT', 'PATCH']:
            # Check modification permissions
            if not can_modify_gig(request.user, gig):
                return Response({
                    'error': 'Permission denied',
                    'detail': 'You cannot modify this gig.'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Tutors can only modify certain fields
            if request.user.is_tutor and not (request.user.is_admin or request.user.is_staff):
                allowed_fields = ['notes']  # Tutors can only update notes
                for field in request.data:
                    if field not in allowed_fields:
                        return Response({
                            'error': 'Permission denied',
                            'detail': f'Tutors can only modify: {", ".join(allowed_fields)}'
                        }, status=status.HTTP_403_FORBIDDEN)
            
            partial = request.method == 'PATCH'
            serializer = GigUpdateSerializer(gig, data=request.data, partial=partial)
            
            if serializer.is_valid():
                # Handle total hours change
                old_total_hours = gig.total_hours
                new_total_hours = serializer.validated_data.get('total_hours', old_total_hours)
                
                if new_total_hours != old_total_hours:
                    # Adjust remaining hours proportionally
                    hours_completed = gig.hours_completed
                    gig.total_hours_remaining = new_total_hours - hours_completed
                
                serializer.save()
                
                logger.info(f"Gig {gig.gig_id} updated by {request.user.email}")
                
                return Response({
                    'message': 'Gig information updated successfully',
                    'gig': GigDetailSerializer(gig).data
                })
            
            return Response({
                'error': 'Validation failed',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        elif request.method == 'DELETE':
            # Only admins can delete gigs
            if not (request.user.is_admin or request.user.is_staff):
                return Response({
                    'error': 'Permission denied',
                    'detail': 'Only administrators can delete gigs.'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Check if gig can be deleted
            if gig.status in ['active']:
                return Response({
                    'error': 'Cannot delete active gig',
                    'detail': 'Please complete or cancel the gig first.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            gig_id_display = gig.gig_id
            gig.delete()
            
            logger.info(f"Gig {gig_id_display} deleted by admin {request.user.email}")
            
            return Response({
                'message': 'Gig deleted successfully'
            }, status=status.HTTP_204_NO_CONTENT)
    
    except Exception as e:
        logger.error(f"Error in gig_detail: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unassigned_gigs(request):
    """
    Get all unassigned gigs (admin only).
    """
    try:
        # Only admins can see unassigned gigs
        if not (request.user.is_admin or request.user.is_staff):
            return Response({
                'error': 'Permission denied',
                'detail': 'Only administrators can view unassigned gigs.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        queryset = Gig.objects.filter(tutor__isnull=True).annotate(
            sessions_count=Count('sessions')
        ).order_by('-created_at')
        
        # Apply filters
        status_filter = request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        priority = request.GET.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Paginate results
        paginator = GigPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = GigListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = GigListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    except Exception as e:
        logger.error(f"Error in unassigned_gigs: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tutor_gigs(request, tutor_id):
    """
    Get all gigs for a specific tutor.
    """
    try:
        # Get tutor
        if tutor_id.startswith('TUT-'):
            try:
                numeric_id = int(tutor_id.split('-')[1])
                tutor = get_object_or_404(Tutor, pk=numeric_id)
            except (ValueError, IndexError):
                return Response({
                    'error': 'Invalid tutor ID format'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            tutor = get_object_or_404(Tutor, pk=tutor_id)
        
        # Check permissions
        can_view = (
            request.user.is_admin or 
            request.user.is_staff or
            (request.user.is_tutor and 
             hasattr(request.user, 'tutor_profile') and 
             request.user.tutor_profile.tutor == tutor)
        )
        
        if not can_view:
            return Response({
                'error': 'Permission denied',
                'detail': 'You can only view your own gigs or be an administrator.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        queryset = Gig.objects.filter(tutor=tutor).annotate(
            sessions_count=Count('sessions')
        ).order_by('-created_at')
        
        # Apply filters
        status_filter = request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Paginate results
        paginator = GigPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = GigListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = GigListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    except Exception as e:
        logger.error(f"Error in tutor_gigs: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_gig(request, gig_id):
    """
    Assign a gig to a tutor (admin only).
    """
    try:
        # Only admins can assign gigs
        if not (request.user.is_admin or request.user.is_staff):
            return Response({
                'error': 'Permission denied',
                'detail': 'Only administrators can assign gigs.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get gig
        if gig_id.startswith('GIG-'):
            try:
                numeric_id = int(gig_id.split('-')[1])
                gig = get_object_or_404(Gig, pk=numeric_id)
            except (ValueError, IndexError):
                return Response({
                    'error': 'Invalid gig ID format'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            gig = get_object_or_404(Gig, pk=gig_id)
        
        # Check if gig is already assigned
        if gig.tutor:
            return Response({
                'error': 'Gig is already assigned',
                'detail': f'Gig is currently assigned to {gig.tutor.full_name}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = GigAssignmentSerializer(data=request.data)
        
        if serializer.is_valid():
            tutor_id = serializer.validated_data['tutor_id']
            notes = serializer.validated_data.get('notes', '')
            
            tutor = Tutor.objects.get(pk=tutor_id)
            gig.tutor = tutor
            
            if notes:
                timestamp = timezone.now().strftime("%Y-%m-%d %H:%M")
                gig.notes += f"\n[{timestamp}] Assigned to {tutor.full_name}: {notes}"
            
            gig.save()
            
            logger.info(f"Gig {gig.gig_id} assigned to tutor {tutor.tutor_id} by {request.user.email}")
            
            return Response({
                'message': f'Gig successfully assigned to {tutor.full_name}',
                'gig': GigDetailSerializer(gig).data
            })
        
        return Response({
            'error': 'Validation failed',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error in assign_gig: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unassign_gig(request, gig_id):
    """
    Unassign a gig from its current tutor (admin only).
    """
    try:
        # Only admins can unassign gigs
        if not (request.user.is_admin or request.user.is_staff):
            return Response({
                'error': 'Permission denied',
                'detail': 'Only administrators can unassign gigs.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get gig
        if gig_id.startswith('GIG-'):
            try:
                numeric_id = int(gig_id.split('-')[1])
                gig = get_object_or_404(Gig, pk=numeric_id)
            except (ValueError, IndexError):
                return Response({
                    'error': 'Invalid gig ID format'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            gig = get_object_or_404(Gig, pk=gig_id)
        
        # Check if gig is assigned
        if not gig.tutor:
            return Response({
                'error': 'Gig is not currently assigned'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if gig is active
        if gig.status == 'active':
            return Response({
                'error': 'Cannot unassign active gig',
                'detail': 'Please put the gig on hold or complete it first.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = GigStatusChangeSerializer(data=request.data)
        
        if serializer.is_valid():
            reason = serializer.validated_data.get('reason', '')
            tutor_name = gig.tutor.full_name
            
            gig.tutor = None
            
            if reason:
                timestamp = timezone.now().strftime("%Y-%m-%d %H:%M")
                gig.notes += f"\n[{timestamp}] Unassigned from {tutor_name}: {reason}"
            
            gig.save()
            
            logger.info(f"Gig {gig.gig_id} unassigned from tutor {tutor_name} by {request.user.email}")
            
            return Response({
                'message': f'Gig successfully unassigned from {tutor_name}',
                'gig': GigDetailSerializer(gig).data
            })
        
        return Response({
            'error': 'Validation failed',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error in unassign_gig: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_gig(request, gig_id):
    """
    Start a gig (admin only).
    """
    try:
        # Only admins can start gigs
        if not (request.user.is_admin or request.user.is_staff):
            return Response({
                'error': 'Permission denied',
                'detail': 'Only administrators can start gigs.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get gig
        if gig_id.startswith('GIG-'):
            try:
                numeric_id = int(gig_id.split('-')[1])
                gig = get_object_or_404(Gig, pk=numeric_id)
            except (ValueError, IndexError):
                return Response({
                    'error': 'Invalid gig ID format'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            gig = get_object_or_404(Gig, pk=gig_id)
        
        # Check if gig can be started
        if gig.status != 'pending':
            return Response({
                'error': f'Cannot start gig with status: {gig.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not gig.tutor:
            return Response({
                'error': 'Cannot start unassigned gig',
                'detail': 'Please assign a tutor first.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        gig.start_gig()
        
        logger.info(f"Gig {gig.gig_id} started by {request.user.email}")
        
        return Response({
            'message': 'Gig started successfully',
            'gig': GigDetailSerializer(gig).data
        })
    
    except Exception as e:
        logger.error(f"Error in start_gig: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_gig(request, gig_id):
    """
    Complete a gig (admin only).
    """
    try:
        # Only admins can complete gigs
        if not (request.user.is_admin or request.user.is_staff):
            return Response({
                'error': 'Permission denied',
                'detail': 'Only administrators can complete gigs.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get gig
        if gig_id.startswith('GIG-'):
            try:
                numeric_id = int(gig_id.split('-')[1])
                gig = get_object_or_404(Gig, pk=numeric_id)
            except (ValueError, IndexError):
                return Response({
                    'error': 'Invalid gig ID format'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            gig = get_object_or_404(Gig, pk=gig_id)
        
        # Check if gig can be completed
        if gig.status not in ['active', 'on_hold']:
            return Response({
                'error': f'Cannot complete gig with status: {gig.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        gig.complete_gig()
        
        logger.info(f"Gig {gig.gig_id} completed by {request.user.email}")
        
        return Response({
            'message': 'Gig completed successfully',
            'gig': GigDetailSerializer(gig).data
        })
    
    except Exception as e:
        logger.error(f"Error in complete_gig: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_gig(request, gig_id):
    """
    Cancel a gig (admin only).
    """
    try:
        # Only admins can cancel gigs
        if not (request.user.is_admin or request.user.is_staff):
            return Response({
                'error': 'Permission denied',
                'detail': 'Only administrators can cancel gigs.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get gig
        if gig_id.startswith('GIG-'):
            try:
                numeric_id = int(gig_id.split('-')[1])
                gig = get_object_or_404(Gig, pk=numeric_id)
            except (ValueError, IndexError):
                return Response({
                    'error': 'Invalid gig ID format'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            gig = get_object_or_404(Gig, pk=gig_id)
        
        # Check if gig can be cancelled
        if gig.status in ['completed', 'cancelled']:
            return Response({
                'error': f'Cannot cancel gig with status: {gig.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = GigStatusChangeSerializer(data=request.data)
        
        if serializer.is_valid():
            reason = serializer.validated_data.get('reason', 'Cancelled by administrator')
            
            gig.cancel_gig(reason)
            
            logger.info(f"Gig {gig.gig_id} cancelled by {request.user.email}. Reason: {reason}")
            
            return Response({
                'message': 'Gig cancelled successfully',
                'gig': GigDetailSerializer(gig).data,
                'reason': reason
            })
        
        return Response({
            'error': 'Validation failed',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error in cancel_gig: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def hold_gig(request, gig_id):
    """
    Put a gig on hold (admin only).
    """
    try:
        # Only admins can put gigs on hold
        if not (request.user.is_admin or request.user.is_staff):
            return Response({
                'error': 'Permission denied',
                'detail': 'Only administrators can put gigs on hold.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get gig
        if gig_id.startswith('GIG-'):
            try:
                numeric_id = int(gig_id.split('-')[1])
                gig = get_object_or_404(Gig, pk=numeric_id)
            except (ValueError, IndexError):
                return Response({
                    'error': 'Invalid gig ID format'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            gig = get_object_or_404(Gig, pk=gig_id)
        
        # Check if gig can be put on hold
        if gig.status != 'active':
            return Response({
                'error': f'Cannot put gig on hold with status: {gig.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = GigStatusChangeSerializer(data=request.data)
        
        if serializer.is_valid():
            reason = serializer.validated_data.get('reason', 'Put on hold by administrator')
            
            gig.put_on_hold(reason)
            
            logger.info(f"Gig {gig.gig_id} put on hold by {request.user.email}. Reason: {reason}")
            
            return Response({
                'message': 'Gig put on hold successfully',
                'gig': GigDetailSerializer(gig).data,
                'reason': reason
            })
        
        return Response({
            'error': 'Validation failed',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error in hold_gig: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def resume_gig(request, gig_id):
    """
    Resume a gig from hold (admin only).
    """
    try:
        # Only admins can resume gigs
        if not (request.user.is_admin or request.user.is_staff):
            return Response({
                'error': 'Permission denied',
                'detail': 'Only administrators can resume gigs.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get gig
        if gig_id.startswith('GIG-'):
            try:
                numeric_id = int(gig_id.split('-')[1])
                gig = get_object_or_404(Gig, pk=numeric_id)
            except (ValueError, IndexError):
                return Response({
                    'error': 'Invalid gig ID format'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            gig = get_object_or_404(Gig, pk=gig_id)
        
        # Check if gig can be resumed
        if gig.status != 'on_hold':
            return Response({
                'error': f'Cannot resume gig with status: {gig.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        gig.resume_gig()
        
        logger.info(f"Gig {gig.gig_id} resumed by {request.user.email}")
        
        return Response({
            'message': 'Gig resumed successfully',
            'gig': GigDetailSerializer(gig).data
        })
    
    except Exception as e:
        logger.error(f"Error in resume_gig: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def adjust_gig_hours(request, gig_id):
    """
    Manually adjust gig hours (admin only).
    """
    try:
        # Only admins can adjust hours
        if not (request.user.is_admin or request.user.is_staff):
            return Response({
                'error': 'Permission denied',
                'detail': 'Only administrators can adjust gig hours.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get gig
        if gig_id.startswith('GIG-'):
            try:
                numeric_id = int(gig_id.split('-')[1])
                gig = get_object_or_404(Gig, pk=numeric_id)
            except (ValueError, IndexError):
                return Response({
                    'error': 'Invalid gig ID format'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            gig = get_object_or_404(Gig, pk=gig_id)
        
        serializer = GigHoursAdjustmentSerializer(data=request.data, context={'gig': gig})
        
        if serializer.is_valid():
            hours_to_subtract = serializer.validated_data['hours_to_subtract']
            reason = serializer.validated_data.get('reason', 'Manual adjustment by administrator')
            
            # Subtract hours
            gig.total_hours_remaining -= hours_to_subtract
            
            # Add to notes
            timestamp = timezone.now().strftime("%Y-%m-%d %H:%M")
            gig.notes += f"\n[{timestamp}] Manual hours adjustment: -{hours_to_subtract} hours. Reason: {reason}"
            
            gig.save()
            
            logger.info(f"Gig {gig.gig_id} hours adjusted by {request.user.email}. Subtracted: {hours_to_subtract}")
            
            return Response({
                'message': f'Successfully subtracted {hours_to_subtract} hours from gig',
                'gig': GigDetailSerializer(gig).data,
                'hours_subtracted': hours_to_subtract,
                'reason': reason
            })
        
        return Response({
            'error': 'Validation failed',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error in adjust_gig_hours: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Gig Sessions Views

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def gig_sessions_list_create(request, gig_id):
    """
    GET: List all sessions for a gig
    POST: Create a new session for a gig
    """
    try:
        print(f"DEBUG: Received gig_id: '{gig_id}' (type: {type(gig_id)})")
        print(f"DEBUG: Request method: {request.method}")
        print(f"DEBUG: Request data: {request.data}")
        
        # Get gig using the helper function
        try:
            numeric_id = parse_gig_id(gig_id)
            print(f"DEBUG: Parsed numeric_id: {numeric_id}")
            gig = get_object_or_404(Gig, pk=numeric_id)
            print(f"DEBUG: Found gig: {gig.gig_id} (DB ID: {gig.id})")
        except ValueError as e:
            print(f"DEBUG: ValueError parsing gig_id: {e}")
            return Response({
                'error': 'Invalid gig ID format'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check permissions
        print(f"DEBUG: User: {request.user.email}, User type: {request.user.user_type}")
        if not can_access_gig(request.user, gig):
            print(f"DEBUG: Permission denied for user {request.user.email}")
            return Response({
                'error': 'Permission denied',
                'detail': 'You can only access sessions for your own gigs or be an administrator.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        print(f"DEBUG: Permission check passed")
        
        if request.method == 'GET':
            print(f"DEBUG: Processing GET request")
            queryset = gig.sessions.all().order_by('-session_date', '-start_time')
            
            # Paginate results
            paginator = SessionPagination()
            page = paginator.paginate_queryset(queryset, request)
            
            if page is not None:
                serializer = GigSessionDetailSerializer(page, many=True)
                return paginator.get_paginated_response(serializer.data)
            
            serializer = GigSessionDetailSerializer(queryset, many=True)
            return Response(serializer.data)
        
        elif request.method == 'POST':
            print(f"DEBUG: Processing POST request")
            
            # Check if user can create sessions
            if not can_modify_gig(request.user, gig):
                print(f"DEBUG: User cannot modify gig")
                return Response({
                    'error': 'Permission denied',
                    'detail': 'You can only create sessions for your own gigs or be an administrator.'
                }, status=status.HTTP_403_FORBIDDEN)
            
            print(f"DEBUG: User can modify gig")
            
            # Add gig to data
            data = request.data.copy()
            data['gig'] = gig.id
            print(f"DEBUG: Modified data with gig ID: {data}")
            
            serializer = GigSessionCreateSerializer(data=data)
            print(f"DEBUG: Created serializer")
            
            if serializer.is_valid():
                print(f"DEBUG: Serializer is valid")
                session = serializer.save()
                
                logger.info(f"New session created for gig {gig.gig_id} by {request.user.email}")
                
                return Response({
                    'message': 'Session created successfully',
                    'session': GigSessionDetailSerializer(session).data
                }, status=status.HTTP_201_CREATED)
            else:
                print(f"DEBUG: Serializer validation failed")
                print(f"DEBUG: Serializer errors: {serializer.errors}")
                
                # Create user-friendly error message
                error_messages = []
                for field, errors in serializer.errors.items():
                    if field == 'non_field_errors':
                        error_messages.extend(errors)
                    else:
                        field_name = field.replace('_', ' ').title()
                        for error in errors:
                            error_messages.append(f"{field_name}: {error}")
                
                user_friendly_message = '; '.join(error_messages) if error_messages else 'Validation failed'
                
                return Response({
                    'error': 'Validation failed',
                    'message': user_friendly_message,  # Add user-friendly message
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        print(f"DEBUG: Exception occurred: {str(e)}")
        print(f"DEBUG: Exception type: {type(e)}")
        import traceback
        traceback.print_exc()
        
        logger.error(f"Error in gig_sessions_list_create: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def gig_session_detail(request, gig_id, session_id):
    """
    GET: Retrieve a specific session
    PUT/PATCH: Update session information
    DELETE: Delete session
    """
    try:
        # Get gig
        if gig_id.startswith('GIG-'):
            try:
                gig_numeric_id = int(gig_id.split('-')[1])
                gig = get_object_or_404(Gig, pk=gig_numeric_id)
            except (ValueError, IndexError):
                return Response({
                    'error': 'Invalid gig ID format'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            gig = get_object_or_404(Gig, pk=gig_id)
        
        # Get session
        if session_id.startswith('SES-'):
            try:
                session_numeric_id = int(session_id.split('-')[1])
                session = get_object_or_404(GigSession, pk=session_numeric_id, gig=gig)
            except (ValueError, IndexError):
                return Response({
                    'error': 'Invalid session ID format'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            session = get_object_or_404(GigSession, pk=session_id, gig=gig)
        
        # Check permissions
        if not can_access_gig(request.user, gig):
            return Response({
                'error': 'Permission denied',
                'detail': 'You can only access sessions for your own gigs or be an administrator.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if request.method == 'GET':
            serializer = GigSessionDetailSerializer(session)
            return Response(serializer.data)
        
        elif request.method in ['PUT', 'PATCH']:
            # Check modification permissions
            if not can_modify_gig(request.user, gig):
                return Response({
                    'error': 'Permission denied',
                    'detail': 'You cannot modify sessions for this gig.'
                }, status=status.HTTP_403_FORBIDDEN)
            
            partial = request.method == 'PATCH'
            serializer = GigSessionSerializer(session, data=request.data, partial=partial)
            
            if serializer.is_valid():
                # Note: The session save method will automatically update gig hours
                serializer.save()
                
                logger.info(f"Session {session.id} for gig {gig.gig_id} updated by {request.user.email}")
                
                return Response({
                    'message': 'Session updated successfully',
                    'session': GigSessionDetailSerializer(session).data
                })
            
            return Response({
                'error': 'Validation failed',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        elif request.method == 'DELETE':
            # Check deletion permissions (admin only)
            if not (request.user.is_admin or request.user.is_staff):
                return Response({
                    'error': 'Permission denied',
                    'detail': 'Only administrators can delete sessions.'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Store hours to add back to gig
            hours_to_restore = session.hours_logged
            session_info = f"Session {session.id} on {session.session_date}"
            
            # Delete session (this will trigger the model's delete method)
            session.delete()
            
            # Restore hours to gig
            gig.total_hours_remaining += hours_to_restore
            gig.save()
            
            logger.info(f"Session deleted from gig {gig.gig_id} by {request.user.email}")
            
            return Response({
                'message': f'{session_info} deleted successfully',
                'hours_restored': hours_to_restore
            }, status=status.HTTP_204_NO_CONTENT)
    
    except Exception as e:
        logger.error(f"Error in gig_session_detail: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_session(request, gig_id, session_id):
    """
    Verify a session - this will subtract hours from the gig's remaining hours.
    """
    try:
        # Only admins can verify sessions
        if not (request.user.is_admin or request.user.is_staff):
            return Response({
                'error': 'Permission denied',
                'detail': 'Only administrators can verify sessions.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get gig
        if gig_id.startswith('GIG-'):
            try:
                gig_numeric_id = int(gig_id.split('-')[1])
                gig = get_object_or_404(Gig, pk=gig_numeric_id)
            except (ValueError, IndexError):
                return Response({
                    'error': 'Invalid gig ID format'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            gig = get_object_or_404(Gig, pk=gig_id)
        
        # Get session
        if session_id.startswith('SES-'):
            try:
                session_numeric_id = int(session_id.split('-')[1])
                session = get_object_or_404(GigSession, pk=session_numeric_id, gig=gig)
            except (ValueError, IndexError):
                return Response({
                    'error': 'Invalid session ID format'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            session = get_object_or_404(GigSession, pk=session_id, gig=gig)
        
        # For the verification system using the model fields
        serializer = SessionVerificationSerializer(
            data=request.data, 
            context={'session': session}
        )
        
        if serializer.is_valid():
            verified = serializer.validated_data['verified']
            notes = serializer.validated_data.get('verification_notes', '')
            
            if verified:
                # Verify session using model method
                if session.verify(request.user):
                    # Add verification note to session
                    if notes:
                        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M")
                        session.session_notes += f"\n[{timestamp}] Verification notes: {notes}"
                        session.save()
                    
                    logger.info(f"Session {session.session_id} verified by {request.user.email}")
                    
                    return Response({
                        'message': 'Session verified successfully',
                        'session': GigSessionDetailSerializer(session).data,
                        'hours_subtracted': session.hours_logged,
                        'gig_hours_remaining': session.gig.total_hours_remaining
                    })
                else:
                    return Response({
                        'error': 'Session is already verified'
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                # Unverify session using model method
                if session.unverify():
                    # Add unverification note
                    if notes:
                        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M")
                        session.session_notes += f"\n[{timestamp}] Unverification notes: {notes}"
                        session.save()
                    
                    logger.info(f"Session {session.session_id} unverified by {request.user.email}")
                    
                    return Response({
                        'message': 'Session unverified successfully',
                        'session': GigSessionDetailSerializer(session).data,
                        'hours_added_back': session.hours_logged,
                        'gig_hours_remaining': session.gig.total_hours_remaining
                    })
                else:
                    return Response({
                        'error': 'Session is not currently verified'
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'error': 'Validation failed',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error in verify_session: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tutor_sessions_list(request, tutor_id):
    """
    GET: List all sessions for a specific tutor across all their gigs
    """
    try:
        # Get tutor
        try:
            tutor = get_object_or_404(Tutor, pk=tutor_id)
        except ValueError:
            return Response({
                'error': 'Invalid tutor ID format'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check permissions - user can only access their own sessions or be admin
        if not (request.user.is_admin or request.user.is_staff or 
                (hasattr(request.user, 'tutor_profile') and request.user.tutor_profile.id == tutor.id)):
            return Response({
                'error': 'Permission denied',
                'detail': 'You can only access your own sessions or be an administrator.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get all sessions for this tutor across all their gigs
        queryset = GigSession.objects.filter(
            gig__tutor=tutor
        ).select_related(
            'gig', 'verified_by'
        ).order_by('-session_date', '-start_time')
        
        # Apply filtering if provided
        # Filter by validation status
        is_verified = request.GET.get('is_verified')
        if is_verified is not None:
            if is_verified.lower() == 'true':
                queryset = queryset.filter(is_verified=True)
            elif is_verified.lower() == 'false':
                queryset = queryset.filter(is_verified=False)
        
        # Filter by date range
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                queryset = queryset.filter(session_date__gte=start_date)
            except ValueError:
                return Response({
                    'error': 'Invalid start_date format. Use YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(session_date__lte=end_date)
            except ValueError:
                return Response({
                    'error': 'Invalid end_date format. Use YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Filter by gig
        gig_id = request.GET.get('gig_id')
        if gig_id:
            if gig_id.startswith('GIG-'):
                try:
                    numeric_id = int(gig_id.split('-')[1])
                    queryset = queryset.filter(gig__pk=numeric_id)
                except (ValueError, IndexError):
                    return Response({
                        'error': 'Invalid gig_id format'
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                queryset = queryset.filter(gig__pk=gig_id)
        
        # Paginate results
        paginator = SessionPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = GigSessionDetailSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = GigSessionDetailSerializer(queryset, many=True)
        return Response(serializer.data)
    
    except Exception as e:
        logger.error(f"Error in tutor_sessions_list: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)