# Updated users/urls.py
from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # Authentication endpoints
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('token/refresh/', views.token_refresh_view, name='token_refresh'),
    
    # User profile endpoints
    path('profile/', views.user_profile_view, name='user_profile'),
    path('profile/update/', views.update_user_profile, name='update_user_profile'),
    path('check-auth/', views.check_auth_view, name='check_auth'),
    
    # Password management
    path('change-password/', views.change_password, name='change_password'),
    path('password-reset/', views.password_reset_request, name='password_reset'),
    
    # Account settings
    path('settings/', views.user_settings, name='user_settings'),
    path('deactivate/', views.deactivate_account, name='deactivate_account'),
]