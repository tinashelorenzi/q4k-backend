from rest_framework import status, filters
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q
from django.db import transaction
from django.utils import timezone
from django.conf import settings
import logging

from .models import Tutor
from users.models import TutorProfile, User
from .serializers import (
    TutorSerializer,
    TutorDetailSerializer,
    TutorListSerializer,
    CreateTutorSerializer,
    TutorUpdateSerializer,
    TutorProfileSerializer,
    TutorStatusSerializer,
)

# Set up logging
logger = logging.getLogger(__name__)


class TutorPagination(PageNumberPagination):
    """Custom pagination for tutors."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def get_client_ip(request):
    """Extract client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def tutors_list_create(request):
    """
    GET: List all tutors with filtering and pagination
    POST: Create a new tutor (admin only)
    """
    try:
        if request.method == 'GET':
            # Get queryset with related data
            queryset = Tutor.objects.select_related('user_profile__user').annotate(
                gigs_count=Count('gigs')
            )
            
            # Apply filters
            search = request.GET.get('search', '')
            if search:
                queryset = queryset.filter(
                    Q(first_name__icontains=search) |
                    Q(last_name__icontains=search) |
                    Q(email_address__icontains=search) |
                    Q(phone_number__icontains=search)
                )
            
            # Filter by status
            is_active = request.GET.get('is_active')
            if is_active is not None:
                queryset = queryset.filter(is_active=is_active.lower() == 'true')
            
            is_blocked = request.GET.get('is_blocked')
            if is_blocked is not None:
                queryset = queryset.filter(is_blocked=is_blocked.lower() == 'true')
            
            # Filter by qualification
            qualification = request.GET.get('qualification')
            if qualification:
                queryset = queryset.filter(highest_qualification=qualification)
            
            # Order by
            ordering = request.GET.get('ordering', '-created_at')
            valid_orderings = [
                'created_at', '-created_at',
                'first_name', '-first_name',
                'last_name', '-last_name',
                'email_address', '-email_address',
                'gigs_count', '-gigs_count'
            ]
            if ordering in valid_orderings:
                queryset = queryset.order_by(ordering)
            
            # Paginate results
            paginator = TutorPagination()
            page = paginator.paginate_queryset(queryset, request)
            
            if page is not None:
                serializer = TutorListSerializer(page, many=True)
                return paginator.get_paginated_response(serializer.data)
            
            serializer = TutorListSerializer(queryset, many=True)
            return Response(serializer.data)
        
        elif request.method == 'POST':
            # Check if user is admin
            if not request.user.is_admin and not request.user.is_staff:
                return Response({
                    'error': 'Permission denied',
                    'detail': 'Only administrators can create tutor accounts.'
                }, status=status.HTTP_403_FORBIDDEN)
            
            serializer = CreateTutorSerializer(data=request.data)
            
            if serializer.is_valid():
                result = serializer.save()
                
                # Log the creation
                logger.info(f"New tutor created by admin {request.user.email}: {result['tutor'].email_address}")
                
                return Response({
                    'message': 'Tutor account created successfully',
                    'tutor': TutorDetailSerializer(result['tutor']).data,
                    'temporary_password': result['temp_password'],
                    'note': 'Please provide the temporary password to the tutor for first login.'
                }, status=status.HTTP_201_CREATED)
            
            return Response({
                'error': 'Validation failed',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error in tutors_list_create: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def tutor_detail(request, tutor_id):
    """
    GET: Retrieve a specific tutor by ID
    PUT/PATCH: Update tutor information
    DELETE: Delete tutor (admin only)
    """
    try:
        # Get tutor by ID or tutor_id format
        if tutor_id.startswith('TUT-'):
            # Extract numeric part from TUT-0001 format
            try:
                numeric_id = int(tutor_id.split('-')[1])
                tutor = get_object_or_404(Tutor, pk=numeric_id)
            except (ValueError, IndexError):
                return Response({
                    'error': 'Invalid tutor ID format'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Assume it's a numeric ID
            tutor = get_object_or_404(Tutor, pk=tutor_id)
        
        if request.method == 'GET':
            serializer = TutorDetailSerializer(tutor)
            return Response(serializer.data)
        
        elif request.method in ['PUT', 'PATCH']:
            # Check permissions - admin or the tutor themselves
            can_edit = (
                request.user.is_admin or 
                request.user.is_staff or
                (hasattr(request.user, 'tutor_profile') and 
                 request.user.tutor_profile.tutor == tutor)
            )
            
            if not can_edit:
                return Response({
                    'error': 'Permission denied',
                    'detail': 'You can only edit your own profile or be an administrator.'
                }, status=status.HTTP_403_FORBIDDEN)
            
            partial = request.method == 'PATCH'
            serializer = TutorUpdateSerializer(tutor, data=request.data, partial=partial)
            
            if serializer.is_valid():
                serializer.save()
                
                # Also update associated user if exists
                try:
                    user_profile = tutor.user_profile
                    if user_profile and user_profile.user:
                        user = user_profile.user
                        user.first_name = tutor.first_name
                        user.last_name = tutor.last_name
                        user.email = tutor.email_address
                        user.phone_number = tutor.phone_number
                        user.save()
                except TutorProfile.DoesNotExist:
                    pass
                
                logger.info(f"Tutor {tutor.tutor_id} updated by {request.user.email}")
                
                return Response({
                    'message': 'Tutor information updated successfully',
                    'tutor': TutorDetailSerializer(tutor).data
                })
            
            return Response({
                'error': 'Validation failed',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        elif request.method == 'DELETE':
            # Only admins can delete tutors
            if not request.user.is_admin and not request.user.is_staff:
                return Response({
                    'error': 'Permission denied',
                    'detail': 'Only administrators can delete tutor accounts.'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Check if tutor has active gigs
            active_gigs = tutor.gigs.filter(status__in=['pending', 'active']).count()
            if active_gigs > 0:
                return Response({
                    'error': 'Cannot delete tutor',
                    'detail': f'Tutor has {active_gigs} active gig(s). Please complete or cancel them first.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            tutor_email = tutor.email_address
            
            # Delete associated user and profile if they exist
            try:
                user_profile = tutor.user_profile
                if user_profile:
                    if user_profile.user:
                        user_profile.user.delete()
                    user_profile.delete()
            except TutorProfile.DoesNotExist:
                pass
            
            tutor.delete()
            
            logger.info(f"Tutor {tutor_email} deleted by admin {request.user.email}")
            
            return Response({
                'message': 'Tutor account deleted successfully'
            }, status=status.HTTP_204_NO_CONTENT)
    
    except Exception as e:
        logger.error(f"Error in tutor_detail: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def my_tutor_info(request):
    """
    Get or update current authenticated user's tutor information.
    Only works if the authenticated user is a tutor.
    """
    try:
        # Check if user is a tutor
        if not request.user.is_tutor:
            return Response({
                'error': 'Permission denied',
                'detail': 'This endpoint is only available for tutor accounts.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get tutor profile
        try:
            tutor_profile = request.user.tutor_profile
            tutor = tutor_profile.tutor
        except TutorProfile.DoesNotExist:
            return Response({
                'error': 'Tutor profile not found',
                'detail': 'No tutor profile is associated with this user account.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if request.method == 'GET':
            serializer = TutorDetailSerializer(tutor)
            return Response(serializer.data)
        
        elif request.method in ['PUT', 'PATCH']:
            partial = request.method == 'PATCH'
            serializer = TutorUpdateSerializer(tutor, data=request.data, partial=partial)
            
            if serializer.is_valid():
                serializer.save()
                
                # Update associated user information
                user = request.user
                user.first_name = tutor.first_name
                user.last_name = tutor.last_name
                user.email = tutor.email_address
                user.phone_number = tutor.phone_number
                user.save()
                
                logger.info(f"Tutor {tutor.tutor_id} updated their own profile")
                
                return Response({
                    'message': 'Your tutor information updated successfully',
                    'tutor': TutorDetailSerializer(tutor).data
                })
            
            return Response({
                'error': 'Validation failed',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error in my_tutor_info: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def block_tutor(request, tutor_id):
    """
    Block a specific tutor (admin only).
    """
    try:
        # Check if user is admin
        if not request.user.is_admin and not request.user.is_staff:
            return Response({
                'error': 'Permission denied',
                'detail': 'Only administrators can block tutors.'
            }, status=status.HTTP_403_FORBIDDEN)
        
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
        
        # Check if already blocked
        if tutor.is_blocked:
            return Response({
                'error': 'Tutor is already blocked'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = TutorStatusSerializer(data=request.data)
        
        if serializer.is_valid():
            reason = serializer.validated_data.get('reason', '')
            
            # Block the tutor
            tutor.block()
            
            # Block associated user if exists
            try:
                user_profile = tutor.user_profile
                if user_profile and user_profile.user:
                    user = user_profile.user
                    user.is_active = False
                    user.save()
            except TutorProfile.DoesNotExist:
                pass
            
            logger.info(f"Tutor {tutor.tutor_id} blocked by admin {request.user.email}. Reason: {reason}")
            
            return Response({
                'message': 'Tutor blocked successfully',
                'tutor': TutorSerializer(tutor).data,
                'reason': reason
            })
        
        return Response({
            'error': 'Validation failed',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error in block_tutor: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unblock_tutor(request, tutor_id):
    """
    Unblock a specific tutor (admin only).
    """
    try:
        # Check if user is admin
        if not request.user.is_admin and not request.user.is_staff:
            return Response({
                'error': 'Permission denied',
                'detail': 'Only administrators can unblock tutors.'
            }, status=status.HTTP_403_FORBIDDEN)
        
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
        
        # Check if not blocked
        if not tutor.is_blocked:
            return Response({
                'error': 'Tutor is not currently blocked'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = TutorStatusSerializer(data=request.data)
        
        if serializer.is_valid():
            reason = serializer.validated_data.get('reason', '')
            
            # Unblock the tutor
            tutor.unblock()
            
            # Reactivate associated user if exists
            try:
                user_profile = tutor.user_profile
                if user_profile and user_profile.user:
                    user = user_profile.user
                    user.is_active = True
                    user.save()
            except TutorProfile.DoesNotExist:
                pass
            
            logger.info(f"Tutor {tutor.tutor_id} unblocked by admin {request.user.email}. Reason: {reason}")
            
            return Response({
                'message': 'Tutor unblocked successfully',
                'tutor': TutorSerializer(tutor).data,
                'reason': reason
            })
        
        return Response({
            'error': 'Validation failed',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error in unblock_tutor: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def tutor_profile(request, tutor_id):
    """
    Get or update tutor profile information.
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
        
        # Get tutor profile
        try:
            profile = tutor.user_profile
        except TutorProfile.DoesNotExist:
            return Response({
                'error': 'Tutor profile not found',
                'detail': 'No profile is associated with this tutor.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if request.method == 'GET':
            serializer = TutorProfileSerializer(profile)
            return Response(serializer.data)
        
        elif request.method in ['PUT', 'PATCH']:
            # Check permissions
            can_edit = (
                request.user.is_admin or 
                request.user.is_staff or
                (hasattr(request.user, 'tutor_profile') and 
                 request.user.tutor_profile.tutor == tutor)
            )
            
            if not can_edit:
                return Response({
                    'error': 'Permission denied',
                    'detail': 'You can only edit your own profile or be an administrator.'
                }, status=status.HTTP_403_FORBIDDEN)
            
            partial = request.method == 'PATCH'
            serializer = TutorProfileSerializer(profile, data=request.data, partial=partial)
            
            if serializer.is_valid():
                serializer.save()
                
                logger.info(f"Tutor profile for {tutor.tutor_id} updated by {request.user.email}")
                
                return Response({
                    'message': 'Tutor profile updated successfully',
                    'profile': serializer.data
                })
            
            return Response({
                'error': 'Validation failed',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error in tutor_profile: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def my_tutor_profile(request):
    """
    Get or update current authenticated user's tutor profile.
    """
    try:
        # Check if user is a tutor
        if not request.user.is_tutor:
            return Response({
                'error': 'Permission denied',
                'detail': 'This endpoint is only available for tutor accounts.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get tutor profile
        try:
            profile = request.user.tutor_profile
        except TutorProfile.DoesNotExist:
            return Response({
                'error': 'Tutor profile not found',
                'detail': 'No tutor profile is associated with this user account.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if request.method == 'GET':
            serializer = TutorProfileSerializer(profile)
            return Response(serializer.data)
        
        elif request.method in ['PUT', 'PATCH']:
            partial = request.method == 'PATCH'
            serializer = TutorProfileSerializer(profile, data=request.data, partial=partial)
            
            if serializer.is_valid():
                serializer.save()
                
                logger.info(f"Tutor {profile.tutor.tutor_id} updated their own profile")
                
                return Response({
                    'message': 'Your tutor profile updated successfully',
                    'profile': serializer.data
                })
            
            return Response({
                'error': 'Validation failed',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error in my_tutor_profile: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def activate_tutor(request, tutor_id):
    """
    Activate a specific tutor (admin only).
    """
    try:
        # Check if user is admin
        if not request.user.is_admin and not request.user.is_staff:
            return Response({
                'error': 'Permission denied',
                'detail': 'Only administrators can activate tutors.'
            }, status=status.HTTP_403_FORBIDDEN)
        
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
        
        # Check if already active
        if tutor.is_active:
            return Response({
                'error': 'Tutor is already active'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if blocked
        if tutor.is_blocked:
            return Response({
                'error': 'Cannot activate blocked tutor',
                'detail': 'Please unblock the tutor first.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Activate the tutor
        tutor.activate()
        
        logger.info(f"Tutor {tutor.tutor_id} activated by admin {request.user.email}")
        
        return Response({
            'message': 'Tutor activated successfully',
            'tutor': TutorSerializer(tutor).data
        })
    
    except Exception as e:
        logger.error(f"Error in activate_tutor: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deactivate_tutor(request, tutor_id):
    """
    Deactivate a specific tutor (admin only).
    """
    try:
        # Check if user is admin
        if not request.user.is_admin and not request.user.is_staff:
            return Response({
                'error': 'Permission denied',
                'detail': 'Only administrators can deactivate tutors.'
            }, status=status.HTTP_403_FORBIDDEN)
        
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
        
        # Check if already inactive
        if not tutor.is_active:
            return Response({
                'error': 'Tutor is already inactive'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check for active gigs
        active_gigs = tutor.gigs.filter(status__in=['pending', 'active']).count()
        if active_gigs > 0:
            return Response({
                'error': 'Cannot deactivate tutor',
                'detail': f'Tutor has {active_gigs} active gig(s). Please complete or transfer them first.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = TutorStatusSerializer(data=request.data)
        
        if serializer.is_valid():
            reason = serializer.validated_data.get('reason', '')
            
            # Deactivate the tutor
            tutor.deactivate()
            
            logger.info(f"Tutor {tutor.tutor_id} deactivated by admin {request.user.email}. Reason: {reason}")
            
            return Response({
                'message': 'Tutor deactivated successfully',
                'tutor': TutorSerializer(tutor).data,
                'reason': reason
            })
        
        return Response({
            'error': 'Validation failed',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error in deactivate_tutor: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred.',
            'details': str(e) if settings.DEBUG else 'Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)