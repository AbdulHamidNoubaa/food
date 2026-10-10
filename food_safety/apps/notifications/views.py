from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.notifications.models import Notification


@login_required
def notification_list(request):
    items = Notification.objects.filter(user=request.user)[:100]
    return render(request, "notifications/list.html", {"notifications": items})


@login_required
@require_http_methods(["POST"])
def mark_read(request, notification_id):
    n = get_object_or_404(Notification, id=notification_id, user=request.user)
    n.is_read = True
    n.save(update_fields=["is_read"])
    return redirect("notifications:list")


@login_required
@require_http_methods(["POST"])
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect("notifications:list")
