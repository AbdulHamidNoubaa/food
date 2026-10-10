from django.urls import path

from apps.dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("", views.municipal_home, name="municipal"),
    path("map/", views.map_view, name="map"),
    path("export/complaints.csv", views.export_complaints_csv, name="export_csv"),
]
