from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView

# --- Admin Interface Customization ---
# This changes the title on the Login screen and the main page
admin.site.site_header = "Pulse Hospital Administration"

# This changes the title in the Browser Tab
admin.site.site_title = "Pulse Admin Portal"

# This changes the "Welcome" text at the top of the dashboard
admin.site.index_title = "Welcome to Pulse Hospital Management System"



urlpatterns = [
    path('pulse-control/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(next_page='/dashboard-redirect/'), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    # Simple include without namespace
    path('', include('pulsehospital.urls')), 
    path('api/', include('api.urls')),
    #install apk path
    path('manifest.json', TemplateView.as_view(template_name="manifest.json", content_type='application/json'), name='manifest.json'),
    path('service-worker.js', TemplateView.as_view(template_name="service-worker.js", content_type='application/javascript'), name='service-worker.js'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])