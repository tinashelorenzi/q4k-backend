from django.urls import path
from . import views

app_name = 'gigs'

urlpatterns = [
    # Analytics endpoint
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    
    # Sessions endpoint for admin
    path('sessions/', views.sessions_list, name='sessions_list'),
    
    # NEW: Tutor Sessions endpoint
    path('sessions/tutor/<str:tutor_id>/', views.tutor_sessions_list, name='tutor_sessions_list'),
    
    # Online Sessions (Virtual Meetings) - MUST be before generic gig routes
    path('online-sessions/', views.online_sessions_list, name='online_sessions_list'),
    path('online-sessions/<int:session_id>/', views.online_session_detail, name='online_session_detail'),
    path('online-sessions/<int:session_id>/extend/', views.online_session_extend, name='online_session_extend'),
    path('online-sessions/<int:session_id>/complete/', views.online_session_complete, name='online_session_complete'),
    path('online-sessions/validate/', views.online_session_validate, name='online_session_validate'),
    path('online-sessions/code/<str:meeting_code>/', views.online_session_by_code, name='online_session_by_code'),
    
    # Gig filtering and assignment (specific routes before generic)
    path('unassigned/', views.unassigned_gigs, name='unassigned_gigs'),
    path('tutor/<str:tutor_id>/', views.tutor_gigs, name='tutor_gigs'),
    
    # Gig CRUD operations
    path('', views.gigs_list_create, name='gigs_list_create'),
    
    # Gig-specific operations (with gig_id)
    path('<str:gig_id>/assign/', views.assign_gig, name='assign_gig'),
    path('<str:gig_id>/unassign/', views.unassign_gig, name='unassign_gig'),
    path('<str:gig_id>/start/', views.start_gig, name='start_gig'),
    path('<str:gig_id>/complete/', views.complete_gig, name='complete_gig'),
    path('<str:gig_id>/cancel/', views.cancel_gig, name='cancel_gig'),
    path('<str:gig_id>/hold/', views.hold_gig, name='hold_gig'),
    path('<str:gig_id>/resume/', views.resume_gig, name='resume_gig'),
    path('<str:gig_id>/adjust-hours/', views.adjust_gig_hours, name='adjust_gig_hours'),
    path('<str:gig_id>/sessions/', views.gig_sessions_list_create, name='gig_sessions_list_create'),
    path('<str:gig_id>/sessions/<str:session_id>/', views.gig_session_detail, name='gig_session_detail'),
    path('<str:gig_id>/sessions/<str:session_id>/verify/', views.verify_session, name='verify_session'),
    
    # Generic gig detail - MUST be last to avoid catching other routes
    path('<str:gig_id>/', views.gig_detail, name='gig_detail'),
]