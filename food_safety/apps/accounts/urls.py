from django.urls import path

from apps.accounts.views import RegisterView, UserLoginView, UserLogoutView, user_list

app_name = "accounts"

urlpatterns = [
    path("login/", UserLoginView.as_view(), name="login"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("register/", RegisterView.as_view(), name="register"),
    path("users/", user_list, name="users"),
]
