from django.urls import path
from . import views

app_name = 'tutors'

urlpatterns = [
    # Tutor CRUD operations
    path('', views.tutors_list_create, name='tutors_list_create'),
    path('<str:tutor_id>/', views.tutor_detail, name='tutor_detail'),
    
    # Current user's tutor information
    path('me/info/', views.my_tutor_info, name='my_tutor_info'),
    path('me/profile/', views.my_tutor_profile, name='my_tutor_profile'),
    
    # Tutor profile operations
    path('<str:tutor_id>/profile/', views.tutor_profile, name='tutor_profile'),
    
    # Tutor status management (admin only)
    path('<str:tutor_id>/block/', views.block_tutor, name='block_tutor'),
    path('<str:tutor_id>/unblock/', views.unblock_tutor, name='unblock_tutor'),
    path('<str:tutor_id>/activate/', views.activate_tutor, name='activate_tutor'),
    path('<str:tutor_id>/deactivate/', views.deactivate_tutor, name='deactivate_tutor'),
]