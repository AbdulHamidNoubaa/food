from apps.notifications.models import Notification


def notify(user, *, type: str, title: str, body: str = "", entity_type: str = "", entity_id: str = ""):
    if user is None:
        return None
    return Notification.objects.create(
        user=user,
        type=type,
        title=title,
        body=body,
        related_entity_type=entity_type,
        related_entity_id=str(entity_id) if entity_id else "",
    )
