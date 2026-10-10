from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

admin.site.site_header = "إدارة نظام سلامة الغذاء"
admin.site.site_title = "Food Safety Admin"
admin.site.index_title = "لوحة الإدارة"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("scan/", include("apps.scans.urls")),
    path("complaints/", include("apps.complaints.urls")),
    path("ingredients/", include("apps.ingredients.urls")),
    path("reference/", include("apps.reference.urls")),
    path("stores/", include("apps.stores.urls")),
    path("products/", include("apps.products.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("municipal/", include("apps.dashboard.urls")),
    path("audit/", include("apps.audit.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
