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
    path('check-auth/', views.check_auth_view, name='check_auth'),
]