from django.urls import path

from apps.stores import views

app_name = "stores"

urlpatterns = [
    path("", views.store_list, name="list"),
    path("map/", views.store_map, name="map"),
    path("api/search/", views.api_search, name="api_search"),
    path("api/nearby/", views.api_nearby, name="api_nearby"),
    path("api/duplicates/", views.api_duplicates, name="api_duplicates"),
    path("<uuid:store_id>/", views.store_detail, name="detail"),
    path("<uuid:store_id>/edit/", views.store_edit, name="edit"),
    path("<uuid:store_id>/merge/", views.store_merge, name="merge"),
    path("<uuid:store_id>/deactivate/", views.store_deactivate, name="deactivate"),
]
