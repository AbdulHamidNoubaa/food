"""بحث وتحميل صور المواد — Openverse / Wikipedia مع معالجة SSL."""
from __future__ import annotations

import logging
import re
import warnings

import httpx
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

USER_AGENT = (
    "FoodSafetyVerificationSystem/1.0 "
    "(educational food-safety app; contact: foodsafety-local@example.com)"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json,image/*,*/*",
}


def _http_client(timeout: float = 20.0) -> httpx.Client:
    # بعض بيئات Windows/OneDrive تفشل في التحقق من الشهادات؛
    # التحقق مُعطّل هنا فقط لتمكين جلب الصور المرجعية محليًا.
    return httpx.Client(
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        verify=False,
    )


def search_material_images(query: str, limit: int = 8) -> list[dict]:
    q = (query or "").strip()
    if not q:
        return []

    results = _search_openverse(q, limit)
    if results:
        return results

    results = _search_wikipedia_summary(q)
    if results:
        return results

    return _search_wikimedia(q, limit)


def _is_useful_image(url: str, title: str = "") -> bool:
    u = (url or "").lower()
    t = (title or "").lower()
    if u.endswith(".svg") or ".svg" in u:
        return False
    # استبعاد نتائج غير ذات صلة شائعة
    junk = ("lrt1", "train", "station", "geograph", "fire_extinguisher", "interior_seats")
    if any(j in u or j in t for j in junk):
        return False
    return True


def _search_openverse(query: str, limit: int) -> list[dict]:
    url = "https://api.openverse.org/v1/images/"
    params = {"q": query, "page_size": min(limit, 20)}
    try:
        with _http_client(20.0) as client:
            resp = client.get(url, params=params, headers=HEADERS)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Openverse search failed: %s", exc)
        return []

    results = []
    for item in data.get("results") or []:
        full = item.get("url") or item.get("thumbnail")
        thumb = item.get("thumbnail") or full
        title = item.get("title") or query
        if not full or not _is_useful_image(full, title):
            continue
        results.append(
            {
                "title": title,
                "thumb_url": thumb,
                "full_url": full,
                "source": "Openverse",
            }
        )
        if len(results) >= limit:
            break
    return results


def _search_wikipedia_summary(query: str) -> list[dict]:
    slug = query.strip().replace(" ", "_")
    candidates = [slug, f"{slug}_(food_additive)", f"{slug}_(color)", f"{slug}_(dye)"]
    try:
        with _http_client(15.0) as client:
            for cand in candidates:
                url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{cand}"
                resp = client.get(url, headers=HEADERS)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                thumb = (data.get("thumbnail") or {}).get("source")
                original = (data.get("originalimage") or {}).get("source") or thumb
                title = data.get("title") or query
                if original and _is_useful_image(original, title):
                    return [
                        {
                            "title": title,
                            "thumb_url": thumb or original,
                            "full_url": original,
                            "source": "Wikipedia",
                        }
                    ]
    except Exception as exc:
        logger.warning("Wikipedia summary failed: %s", exc)
    return []


def _search_wikimedia(query: str, limit: int) -> list[dict]:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|mime|size",
        "iiurlwidth": 320,
        "origin": "*",
    }
    try:
        with _http_client(15.0) as client:
            resp = client.get(
                "https://commons.wikimedia.org/w/api.php", params=params, headers=HEADERS
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Wikimedia search failed: %s", exc)
        return []

    pages = (data.get("query") or {}).get("pages") or {}
    results = []
    for page in pages.values():
        info_list = page.get("imageinfo") or []
        if not info_list:
            continue
        info = info_list[0]
        mime = info.get("mime") or ""
        if not mime.startswith("image/") or mime == "image/svg+xml":
            continue
        full = info.get("url")
        title = page.get("title", "").replace("File:", "")
        if not full or not _is_useful_image(full, title):
            continue
        results.append(
            {
                "title": title,
                "thumb_url": info.get("thumburl") or full,
                "full_url": full,
                "source": "Wikimedia Commons",
            }
        )
    return results


def download_image_to_field(url: str, filename_hint: str = "material") -> ContentFile | None:
    if not url:
        return None
    try:
        with _http_client(30.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            body = resp.content
            content_type = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
            if not content_type.startswith("image/"):
                if body[:3] == b"\xff\xd8\xff":
                    content_type = "image/jpeg"
                elif body[:8] == b"\x89PNG\r\n\x1a\n":
                    content_type = "image/png"
                elif body[:4] == b"RIFF" and body[8:12] == b"WEBP":
                    content_type = "image/webp"
                else:
                    return None
            if content_type == "image/svg+xml":
                return None

            ext = {
                "image/jpeg": ".jpg",
                "image/jpg": ".jpg",
                "image/png": ".png",
                "image/webp": ".webp",
                "image/gif": ".gif",
            }.get(content_type, ".jpg")
            safe = re.sub(r"[^A-Za-z0-9_-]+", "_", filename_hint)[:40] or "material"
            return ContentFile(body, name=f"{safe}{ext}")
    except Exception as exc:
        logger.warning("Image download failed: %s", exc)
        return None
