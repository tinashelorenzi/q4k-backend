"""
URL configuration for quest4knowledge project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Admin interface
    path('admin/', admin.site.urls),
    
    # API endpoints
    path('api/auth/', include('users.urls')),
    path('api/tutors/', include('tutors.urls')),
    path('api/gigs/', include('gigs.urls')),
    
    # Alternative session endpoints for easier access
    path('api/sessions/', include('gigs.urls')),  # This will make /api/sessions/tutor/<id>/ work
    
    # Health check endpoint (optional)
    path('api/health/', lambda request: 
         __import__('django.http').http.JsonResponse({'status': 'ok'})),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)