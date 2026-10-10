from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect, render

from apps.accounts.models import Role
from apps.audit.models import AuditLog


@login_required
def audit_list(request):
    if request.user.role != Role.ADMIN and not request.user.is_superuser:
        return redirect("core:home")
    qs = AuditLog.objects.select_related("user").all()
    action = request.GET.get("action", "").strip()
    if action:
        qs = qs.filter(action__icontains=action)
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(request, "audit/list.html", {"page_obj": page, "action": action})
