from django.urls import path

from apps.reference import views

app_name = "reference"

urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("sync/", views.sync_reference, name="sync"),
    path("sync/logs/", views.sync_logs, name="sync_logs"),
    path("<uuid:additive_id>/", views.additive_detail, name="detail"),
    path("<uuid:additive_id>/override/", views.override_edit, name="override"),
]
