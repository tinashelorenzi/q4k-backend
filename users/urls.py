# Updated users/urls.py
from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # Authentication endpoints
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('token/refresh/', views.token_refresh_view, name='token_refresh'),
    
    # User management endpoints (admin only)
    path('', views.users_list, name='users_list'),
    path('create-tutor/', views.create_tutor_user, name='create_tutor_user'),
    path('<int:user_id>/', views.update_user, name='update_user'),
    path('<int:user_id>/deactivate/', views.deactivate_user, name='deactivate_user'),
    path('<int:user_id>/activate/', views.activate_user, name='activate_user'),
    path('<int:user_id>/delete/', views.delete_user, name='delete_user'),
    
    # User profile endpoints
    path('profile/', views.user_profile_view, name='user_profile'),
    path('profile/update/', views.update_user_profile, name='update_user_profile'),
    path('check-auth/', views.check_auth_view, name='check_auth'),
    
    # Password management
    path('change-password/', views.change_password, name='change_password'),
    
    # Password reset endpoints
    path('password-reset/request/', views.request_password_reset, name='request_password_reset'),
    path('password-reset/verify/', views.verify_reset_token, name='verify_reset_token'),
    path('password-reset/reset/', views.reset_password, name='reset_password'),
    
    # Account settings
    path('settings/', views.user_settings, name='user_settings'),
    path('deactivate/', views.deactivate_account, name='deactivate_account'),

    # Batch import endpoints
    path('batch-import/', views.batch_tutor_import, name='batch_tutor_import'),
    path('verify-token/', views.verify_setup_token, name='verify_setup_token'),
    path('complete-setup/', views.complete_account_setup, name='complete_account_setup'),
    path('import-history/', views.batch_import_history, name='batch_import_history'),
]