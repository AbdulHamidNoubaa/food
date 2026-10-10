"""OCR pipeline: preprocessing + text extraction. No safety decisions here."""
from __future__ import annotations

import os
import re
import shutil
import time
from typing import Any

from django.conf import settings
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


E_TOKEN_RE = re.compile(r"\bE[-\s]?\d{3,4}[a-zA-Z]?\b", re.IGNORECASE)
SPLIT_RE = re.compile(r"[,;\n،؛|/]+")

# Common Windows install locations (UB Mannheim installer)
_TESSERACT_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\{user}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
]


def _configure_tesseract(pytesseract_mod) -> str | None:
    """Point pytesseract at the binary if not already on PATH."""
    configured = getattr(settings, "TESSERACT_CMD", "") or os.environ.get("TESSERACT_CMD", "")
    if configured and os.path.isfile(configured):
        pytesseract_mod.pytesseract.tesseract_cmd = configured
        return configured
    which = shutil.which("tesseract")
    if which:
        pytesseract_mod.pytesseract.tesseract_cmd = which
        return which
    user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    for path in _TESSERACT_CANDIDATES:
        path = path.format(user=user)
        if os.path.isfile(path):
            pytesseract_mod.pytesseract.tesseract_cmd = path
            return path
    return None


def preprocess_image(image: Image.Image) -> Image.Image:
    """Enhance label text for OCR. No safety logic."""
    img = ImageOps.exif_transpose(image.convert("RGB"))
    # Upscale small images (phone crops / synthetic labels)
    w, h = img.size
    min_side = min(w, h)
    if min_side < 900:
        scale = 900 / min_side
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    gray = ImageOps.grayscale(img)
    gray = ImageOps.autocontrast(gray)
    gray = ImageEnhance.Contrast(gray).enhance(1.6)
    gray = gray.filter(ImageFilter.SHARPEN)
    # Cap large side for speed
    max_side = 2000
    w, h = gray.size
    if max(w, h) > max_side:
        ratio = max_side / max(w, h)
        gray = gray.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
    return gray.convert("RGB")


def _try_tesseract(img: Image.Image) -> tuple[str, float, str]:
    try:
        import pytesseract
    except ImportError:
        return (
            "",
            0.0,
            "tesseract_unavailable:ModuleNotFoundError",
        )

    cmd = _configure_tesseract(pytesseract)
    if not cmd:
        return (
            "",
            0.0,
            "tesseract_unavailable:BinaryNotFound",
        )

    # Prefer English for food labels (E-numbers); try Arabic+English if available
    lang_attempts = ["eng", "ara+eng", "osd"]
    last_err = ""
    for lang in lang_attempts:
        try:
            config = "--psm 6"
            raw = pytesseract.image_to_string(img, lang=lang, config=config)
            if not (raw or "").strip() and lang == "eng":
                # Sparse layout retry
                raw = pytesseract.image_to_string(img, lang=lang, config="--psm 4")
            data = pytesseract.image_to_data(
                img, lang=lang, config=config, output_type=pytesseract.Output.DICT
            )
            confs = [
                int(c)
                for c in data.get("conf", [])
                if str(c).lstrip("-").isdigit() and int(c) >= 0
            ]
            overall = (sum(confs) / len(confs) / 100.0) if confs else (0.7 if raw.strip() else 0.0)
            if raw.strip():
                return raw, overall, f"tesseract:{lang}"
        except Exception as exc:
            last_err = f"{exc.__class__.__name__}:{exc}"
            continue
    return "", 0.0, f"tesseract_failed:{last_err or 'empty'}"


def tokenize_ingredients(raw_text: str) -> list[str]:
    if not raw_text:
        return []
    lower = raw_text.lower()
    for marker in ("ingredients", "ingredient list", "المكونات", "مكونات", "contains"):
        idx = lower.find(marker)
        if idx >= 0:
            raw_text = raw_text[idx + len(marker) :]
            raw_text = raw_text.lstrip(" :：-–")
            break

    tokens = []
    for part in SPLIT_RE.split(raw_text):
        part = part.strip(" .\t-–•*|()")
        if len(part) < 2:
            continue
        low = part.lower()
        if any(
            noise in low
            for noise in (
                "food safety test",
                "ocr sample",
                "not a real product",
                "expected ",
                "barcode ",
                "ingredient list",
            )
        ):
            continue
        e_matches = E_TOKEN_RE.findall(part)
        if e_matches:
            for e in e_matches:
                tokens.append(e.upper().replace(" ", "").replace("-", ""))
            cleaned = E_TOKEN_RE.sub("", part).strip(" ,،()")
            # Keep meaningful chemical names
            if len(cleaned) > 3 and cleaned.lower() not in {"colour", "color", "acid"}:
                tokens.append(cleaned)
        else:
            tokens.append(part)

    seen = set()
    out = []
    for t in tokens:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out


def apply_confidence_gate(tokens: list[str], overall: float) -> list[dict[str, Any]]:
    min_conf = getattr(settings, "MIN_OCR_CONFIDENCE", 0.65)
    human_min = getattr(settings, "HUMAN_VERIFY_MIN", 0.50)
    results = []
    for t in tokens:
        conf = float(overall)
        # E-numbers are high-signal even with modest overall OCR confidence
        if E_TOKEN_RE.fullmatch(t.replace(" ", "")):
            conf = max(conf, 0.75)
        needs = human_min <= conf < min_conf
        if conf < human_min:
            results.append(
                {
                    "text": t,
                    "confidence": conf,
                    "needs_verification": True,
                    "low_confidence": True,
                }
            )
        else:
            results.append(
                {
                    "text": t,
                    "confidence": conf,
                    "needs_verification": needs,
                    "low_confidence": False,
                }
            )
    return results


def _try_rapidocr(img: Image.Image) -> tuple[str, float, str]:
    """Pip-only OCR fallback (no system Tesseract required)."""
    try:
        from rapidocr_onnxruntime import RapidOCR
        import numpy as np
    except ImportError:
        return "", 0.0, "rapidocr_unavailable:ImportError"

    try:
        engine = RapidOCR()
        arr = np.array(img.convert("RGB"))
        result, _elapse = engine(arr)
        if not result:
            return "", 0.0, "rapidocr:empty"
        lines = []
        scores = []
        for item in result:
            # item: [box, text, score]
            if len(item) >= 3:
                text, score = item[1], float(item[2])
            else:
                continue
            if text and str(text).strip():
                lines.append(str(text).strip())
                scores.append(score)
        raw = "\n".join(lines)
        overall = (sum(scores) / len(scores)) if scores else 0.0
        return raw, overall, "rapidocr"
    except Exception as exc:
        return "", 0.0, f"rapidocr_failed:{exc.__class__.__name__}"


def _user_message(engine: str) -> str:
    if "BinaryNotFound" in engine or "ModuleNotFoundError" in engine:
        return (
            "تعذر تشغيل محرك قراءة الملصق على هذا الجهاز. "
            "أعد المحاولة بصورة أوضح، أو أدخل قائمة المكونات يدويًا."
        )
    if "failed" in engine or engine.endswith(":empty"):
        return "تعذر قراءة النص من الصورة. جرّب صورة أوضح أو أدخل النص يدويًا."
    return "يرجى التقاط صورة أوضح لقائمة المكونات، أو إدخال النص يدويًا."


def extract_from_image(file_obj) -> dict:
    """
    AI/OCR responsibility ONLY:
    image → preprocess → OCR → normalize/tokenize → confidence list
    Never returns a safety decision.
    """
    started = time.perf_counter()
    image = Image.open(file_obj)
    processed = preprocess_image(image)

    raw, overall, engine = _try_tesseract(processed)
    if not raw.strip():
        raw2, overall2, engine2 = _try_rapidocr(processed)
        if raw2.strip():
            raw, overall, engine = raw2, overall2, engine2
        else:
            engine = f"{engine}|{engine2}"

    if not raw.strip():
        elapsed = int((time.perf_counter() - started) * 1000)
        return {
            "raw_text": "",
            "extracted_ingredients": [],
            "overall_confidence": 0.0,
            "processing_time_ms": elapsed,
            "engine_note": engine,
            "message": _user_message(engine),
        }

    tokens = tokenize_ingredients(raw)
    # If tokenization dropped everything but raw has E-numbers, pull them
    if not tokens:
        tokens = [e.upper().replace(" ", "").replace("-", "") for e in E_TOKEN_RE.findall(raw)]
    extracted = apply_confidence_gate(tokens, overall)
    elapsed = int((time.perf_counter() - started) * 1000)
    return {
        "raw_text": raw.strip(),
        "extracted_ingredients": extracted,
        "overall_confidence": round(overall, 3),
        "processing_time_ms": elapsed,
        "engine_note": engine,
        "message": "",
    }


def extract_from_manual_text(text: str) -> dict:
    """Manual text path — still no AI, still no safety decision."""
    tokens = tokenize_ingredients(text)
    extracted = [
        {"text": t, "confidence": 1.0, "needs_verification": False, "low_confidence": False}
        for t in tokens
    ]
    return {
        "raw_text": text,
        "extracted_ingredients": extracted,
        "overall_confidence": 1.0,
        "processing_time_ms": 0,
        "engine_note": "manual_text",
        "message": "",
    }
