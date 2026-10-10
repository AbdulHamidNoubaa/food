from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.notifications.models import Notification
from apps.scans.models import ProductScan


def home(request):
    if request.user.is_authenticated and request.user.is_municipal_staff:
        return redirect("dashboard:municipal")

    unread = 0
    recent = []
    if request.user.is_authenticated:
        unread = Notification.objects.filter(user=request.user, is_read=False).count()
        recent = (
            ProductScan.objects.filter(user=request.user)
            .select_related("assessment", "product")[:5]
        )
    return render(
        request,
        "core/home.html",
        {"unread": unread, "recent": recent},
    )


@login_required
def profile(request):
    recent = ProductScan.objects.filter(user=request.user).select_related("assessment")[:10]
    return render(request, "core/profile.html", {"recent": recent})
