from django.urls import path

from apps.ingredients import views

app_name = "ingredients"

urlpatterns = [
    path("", views.ingredient_list, name="list"),
    path("banned/", views.banned_list, name="banned"),
    path("banned/add/", views.banned_create, name="banned_create"),
    path("banned/<uuid:ingredient_id>/edit/", views.banned_edit, name="banned_edit"),
    path("banned/image-search/", views.image_search_api, name="image_search"),
    path("banned/duplicate-check/", views.duplicate_check_api, name="duplicate_check"),
    path("unmatched/", views.unmatched_list, name="unmatched"),
    path("<uuid:ingredient_id>/", views.ingredient_detail, name="detail"),
]
