from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView

from apps.accounts.forms import LoginForm, RegisterForm
from apps.accounts.models import Role, User


class UserLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm


class UserLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")


class RegisterView(CreateView):
    form_class = RegisterForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("core:home")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response


@login_required
def user_list(request):
    if request.user.role != Role.ADMIN and not request.user.is_superuser:
        return redirect("core:home")
    q = request.GET.get("q", "").strip()
    role = request.GET.get("role", "").strip()
    qs = User.objects.all().order_by("-date_joined")
    if q:
        qs = qs.filter(
            Q(username__icontains=q) | Q(full_name__icontains=q) | Q(email__icontains=q)
        )
    if role:
        qs = qs.filter(role=role)
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/users.html",
        {"page_obj": page, "q": q, "role": role, "role_choices": Role.choices},
    )
