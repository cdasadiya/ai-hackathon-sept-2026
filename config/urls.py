from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

from app.views import blood_report_media

urlpatterns = [
    path("admin/", admin.site.urls),
    # Always routed: django's static() helper is a no-op when DEBUG=False.
    path("media/blood_reports/<path:path>", blood_report_media, name="blood_report_media"),
    path("", include("app.urls")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
