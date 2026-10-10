from apps.audit.models import AuditLog


SENSITIVE_PATH_PREFIXES = (
    "/admin/",
    "/ingredients/",
    "/municipal/",
    "/complaints/",
)


class AuditMiddleware:
    """Lightweight request tagging; detailed writes go through log_action()."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_action(request=None, *, user=None, action: str, entity_type: str = "", entity_id: str = "", old_value=None, new_value=None):
    if request is not None and user is None:
        user = getattr(request, "user", None)
        if user is not None and not user.is_authenticated:
            user = None
    ip = client_ip(request) if request is not None else None
    device = ""
    if request is not None:
        device = request.META.get("HTTP_USER_AGENT", "")[:500]
    return AuditLog.objects.create(
        user=user,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else "",
        old_value=old_value,
        new_value=new_value,
        ip_address=ip,
        device_info=device,
    )
