from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth APIs
    path('api/auth/', include('accounts.urls')),

    # Other APIs
    path('api/slots/', include('slots.urls')),
    path('api/', include('transactions.urls')),
    path('api/', include('bookings.urls')),
    path('api/payment/', include('payments.urls')),

    # 4 Interfaces
    path('', include('user_portal.urls')),
    path('admin-panel/', include('admin_panel.urls')),
    path('gate/', include('gate.urls')),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) \
  + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)