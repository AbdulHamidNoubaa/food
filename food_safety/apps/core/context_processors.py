from django.urls import reverse

from apps.accounts.models import Role
from apps.notifications.models import Notification


def _item(label, url_name, icon, match_prefixes=None):
    return {
        "label": label,
        "url_name": url_name,
        "icon": icon,
        "match_prefixes": match_prefixes or [],
    }


def build_nav(user):
    if not user.is_authenticated:
        return []

    role = user.role
    verify = _item("التحقق من منتج", "scans:hub", "scan-barcode", ["/scan/"])
    my_scans = _item("سجل التحقق", "scans:my_scans", "history", ["/scan/mine/"])
    products = _item("المنتجات", "products:list", "package", ["/products/"])
    banned = _item("المواد المحظورة", "ingredients:banned", "shield-alert", ["/ingredients/"])
    reference = _item("القاعدة المرجعية", "reference:catalog", "book-open", ["/reference/"])
    complaints_mine = _item("بلاغاتي", "complaints:mine", "file-text", ["/complaints/mine"])
    complaints_all = _item("البلاغات", "complaints:all", "clipboard-list", ["/complaints/"])
    dashboard = _item("لوحة التحكم", "dashboard:municipal", "layout-dashboard", ["/municipal/"])
    map_page = _item("الخريطة الرقابية", "dashboard:map", "map-pin", ["/municipal/map"])
    audit = _item("سجل العمليات", "audit:list", "scroll-text", ["/audit/"])
    users = _item("المستخدمون", "accounts:users", "users", ["/accounts/users"])
    stores = _item("المنشآت", "stores:list", "store", ["/stores/"])
    stores_map = _item("خريطة المنشآت", "stores:map", "map", ["/stores/map"])
    notifications = _item("الإشعارات", "notifications:list", "bell", ["/notifications/"])
    profile = _item("الحساب", "core:profile", "user-cog", ["/profile/"])

    if role == Role.USER:
        return [verify, my_scans, complaints_mine, notifications, profile]

    if role == Role.INSPECTOR:
        return [dashboard, complaints_all, products, stores, stores_map, reference, banned, map_page, verify, notifications, profile]

    if role == Role.MUNICIPAL_OFFICER:
        return [dashboard, complaints_all, map_page, stores, stores_map, products, notifications, profile]

    if role == Role.FOOD_SAFETY_SPECIALIST:
        return [dashboard, products, stores, reference, banned, complaints_all, verify, notifications, profile]

    # ADMIN
    return [
        dashboard,
        verify,
        products,
        reference,
        banned,
        complaints_all,
        map_page,
        stores,
        stores_map,
        audit,
        users,
        notifications,
        profile,
    ]


def site_context(request):
    unread = 0
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        unread = Notification.objects.filter(user=user, is_read=False).count()

    nav_items = []
    path = getattr(request, "path", "")
    for item in build_nav(user) if user and user.is_authenticated else []:
        try:
            url = reverse(item["url_name"])
        except Exception:
            continue
        active = path == url or any(path.startswith(p) for p in item["match_prefixes"])
        if item["url_name"] == "stores:list" and path.startswith("/stores/map"):
            active = False
        if item["url_name"] == "stores:map":
            active = path.startswith("/stores/map")
        # avoid marking all /scan/ active for my_scans only when on mine
        if item["url_name"] == "scans:hub" and path.startswith("/scan/mine"):
            active = False
        if item["url_name"] == "complaints:all" and path.startswith("/complaints/mine"):
            active = False
        if item["url_name"] == "complaints:mine":
            active = path.startswith("/complaints/mine")
        nav_items.append({**item, "url": url, "active": active})

    return {
        "unread_notifications": unread,
        "app_name_ar": "نظام التحقق من سلامة الغذاء",
        "app_name_en": "Food Safety Verification System",
        "nav_items": nav_items,
        "use_app_shell": bool(user and user.is_authenticated),
    }
