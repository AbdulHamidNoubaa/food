from django.urls import path

from apps.complaints import views

app_name = "complaints"

urlpatterns = [
    path("", views.all_complaints, name="all"),
    path("from-scan/<uuid:scan_id>/", views.create_complaint, name="create"),
    path("mine/", views.my_complaints, name="mine"),
    path("<uuid:complaint_id>/", views.complaint_detail, name="detail"),
    path("<uuid:complaint_id>/status/", views.update_complaint_status, name="update_status"),
]
