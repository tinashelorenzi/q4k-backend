from django.urls import path
from . import views

app_name = 'gigs'

urlpatterns = [
    # Gig CRUD operations
    path('', views.gigs_list_create, name='gigs_list_create'),
    path('<str:gig_id>/', views.gig_detail, name='gig_detail'),
    
    # Gig filtering and assignment
    path('unassigned/', views.unassigned_gigs, name='unassigned_gigs'),
    path('tutor/<str:tutor_id>/', views.tutor_gigs, name='tutor_gigs'),
    
    # Gig assignment operations (admin only)
    path('<str:gig_id>/assign/', views.assign_gig, name='assign_gig'),
    path('<str:gig_id>/unassign/', views.unassign_gig, name='unassign_gig'),
    
    # Gig status management (admin only)
    path('<str:gig_id>/start/', views.start_gig, name='start_gig'),
    path('<str:gig_id>/complete/', views.complete_gig, name='complete_gig'),
    path('<str:gig_id>/cancel/', views.cancel_gig, name='cancel_gig'),
    path('<str:gig_id>/hold/', views.hold_gig, name='hold_gig'),
    path('<str:gig_id>/resume/', views.resume_gig, name='resume_gig'),
    
    # Gig hours adjustment (admin only)
    path('<str:gig_id>/adjust-hours/', views.adjust_gig_hours, name='adjust_gig_hours'),
    
    # Gig Sessions
    path('<str:gig_id>/sessions/', views.gig_sessions_list_create, name='gig_sessions_list_create'),
    path('<str:gig_id>/sessions/<str:session_id>/', views.gig_session_detail, name='gig_session_detail'),
    
    # Session verification (admin only)
    path('<str:gig_id>/sessions/<str:session_id>/verify/', views.verify_session, name='verify_session'),
]