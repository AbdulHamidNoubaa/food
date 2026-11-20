"""Render thesis UML diagrams for the food-safety system. Run from repo root."""
from __future__ import annotations

import os
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
SCALE = 2

NAVY = "#1B3A4B"
TEAL = "#0E6B67"
CLAY = "#8C3D32"
INK = "#1C2430"
MUTED = "#5C6770"
LINE = "#2C3A46"
PAPER = "#F6F3EC"
WHITE = "#FFFFFF"
GOLD = "#F3E6C8"
SOFT = "#E7EEF1"
WARN = "#F8EBE6"


def ar(text: str) -> str:
    if not text:
        return ""
    return get_display(arabic_reshaper.reshape(text))


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "tahomabd.ttf" if bold else "tahoma.ttf"
    path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name)
    return ImageFont.truetype(path, size * SCALE)


class Board:
    def __init__(self, w: int, h: int, title: str, subtitle: str = ""):
        self.w, self.h = w, h
        self.im = Image.new("RGB", (w * SCALE, h * SCALE), PAPER)
        self.d = ImageDraw.Draw(self.im)
        self.title_font = font(22, True)
        self.sub_font = font(13)
        self.body = font(13)
        self.small = font(11)
        self.tiny = font(10)
        self.bold = font(13, True)
        self.head = font(14, True)
        self.d.rectangle((0, 0, w * SCALE, 58 * SCALE), fill=NAVY)
        self.d.text((18 * SCALE, 10 * SCALE), ar(title), font=self.title_font, fill=WHITE)
        if subtitle:
            self.d.text((18 * SCALE, 36 * SCALE), ar(subtitle), font=self.sub_font, fill="#D5E2E8")

    def save(self, name: str):
        path = OUT / name
        self.im.save(path, "PNG", dpi=(180, 180))
        print(path.name, self.im.size)

    def text(self, xy, text, fnt=None, fill=INK, anchor="lt"):
        self.d.text(
            (xy[0] * SCALE, xy[1] * SCALE),
            ar(text),
            font=fnt or self.body,
            fill=fill,
            anchor=anchor,
        )

    def rect(self, box, fill=WHITE, outline=LINE, width=2):
        x, y, w, h = box
        self.d.rectangle(
            (x * SCALE, y * SCALE, (x + w) * SCALE, (y + h) * SCALE),
            fill=fill,
            outline=outline,
            width=width * SCALE // 2 or 1,
        )

    def round(self, box, r, fill=WHITE, outline=LINE, width=2):
        x, y, w, h = box
        self.d.rounded_rectangle(
            (x * SCALE, y * SCALE, (x + w) * SCALE, (y + h) * SCALE),
            radius=r * SCALE,
            fill=fill,
            outline=outline,
            width=max(1, width * SCALE // 2),
        )

    def line(self, a, b, fill=LINE, width=2):
        self.d.line(
            (a[0] * SCALE, a[1] * SCALE, b[0] * SCALE, b[1] * SCALE),
            fill=fill,
            width=max(1, width * SCALE // 2),
        )

    def dashed(self, a, b, fill=MUTED, width=1, dash=8):
        x1, y1 = a
        x2, y2 = b
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 or 1
        ux, uy = (x2 - x1) / length, (y2 - y1) / length
        pos = 0
        while pos < length:
            end = min(pos + dash, length)
            self.line((x1 + ux * pos, y1 + uy * pos), (x1 + ux * end, y1 + uy * end), fill, width)
            pos += dash * 2

    def arrow(self, a, b, fill=LINE, width=2):
        self.line(a, b, fill, width)
        import math

        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        size = 9
        for delta in (2.6, -2.6):
            x = b[0] - size * math.cos(ang + delta / 3)
            y = b[1] - size * math.sin(ang + delta / 3)
            self.line(b, (x, y), fill, width)

    def ellipse(self, box, fill=WHITE, outline=TEAL):
        x, y, w, h = box
        self.d.ellipse(
            (x * SCALE, y * SCALE, (x + w) * SCALE, (y + h) * SCALE),
            fill=fill,
            outline=outline,
            width=2 * SCALE // 2,
        )

    def actor(self, x, y, name):
        # stick figure centered at x, head top y
        self.d.ellipse(
            ((x - 12) * SCALE, y * SCALE, (x + 12) * SCALE, (y + 24) * SCALE),
            outline=NAVY,
            width=2 * SCALE // 2,
        )
        self.line((x, y + 24), (x, y + 52), NAVY, 2)
        self.line((x - 18, y + 36), (x + 18, y + 36), NAVY, 2)
        self.line((x, y + 52), (x - 16, y + 74), NAVY, 2)
        self.line((x, y + 52), (x + 16, y + 74), NAVY, 2)
        self.text((x, y + 82), name, self.small, NAVY, anchor="mt")

    def klass(self, x, y, w, name, attrs, stereotype=""):
        line_h = 15
        head_h = 36 if stereotype else 26
        body_h = 8 + line_h * max(1, len(attrs))
        h = head_h + body_h
        self.rect((x, y, w, h), WHITE, NAVY, 2)
        self.rect((x, y, w, head_h), NAVY, NAVY, 1)
        if stereotype:
            self.text((x + w / 2, y + 3), stereotype, self.tiny, "#D5E2E8", anchor="mt")
            self.text((x + w / 2, y + 16), name, self.bold, WHITE, anchor="mt")
        else:
            self.text((x + w / 2, y + 5), name, self.bold, WHITE, anchor="mt")
        yy = y + head_h + 4
        for attr in attrs:
            self.text((x + 8, yy), attr, self.tiny, INK)
            yy += line_h
        return {"x": x, "y": y, "w": w, "h": h,
                "top": (x + w / 2, y), "bot": (x + w / 2, y + h),
                "left": (x, y + h / 2), "right": (x + w, y + h / 2)}


def _oval(b, x, y, w, h, label, outline):
    b.ellipse((x, y, w, h), WHITE, outline)
    b.text((x + w / 2, y + h / 2), label, b.small, INK, anchor="mm")


def usecase():
    b = Board(1700, 1120, "مخطط حالات الاستخدام", "الارتباط إلى المجموعة، وتفصيل الصلاحية في الملاحظة أسفل المخطط")
    b.round((210, 84, 1280, 860), 18, "#FBF9F4", NAVY, 2)
    b.text((850, 98), "نظام التحقق من سلامة الغذاء", b.head, NAVY, anchor="mt")

    groups = [
        (240, 140, 1220, 250, SOFT, TEAL, "التحقق العام: زائر غير مسجّل ومستهلك"),
        (240, 408, 1220, 250, "#F8F1E4", CLAY, "البلاغ والرقابة"),
        (240, 676, 1220, 230, WARN, NAVY, "البيانات والإدارة"),
    ]
    for x, y, w, h, fill, outline, title in groups:
        b.round((x, y, w, h), 12, fill, outline, 2)
        b.text((x + 16, y + 10), title, b.bold, outline)

    ow, oh = 270, 64
    public = [
        (270, 188, "تسجيل حساب"),
        (570, 188, "تسجيل الدخول والخروج"),
        (870, 188, "فحص بالباركود"),
        (1170, 188, "بحث عن منتج"),
        (270, 282, "فحص بصورة الملصق"),
        (570, 282, "تأكيد قراءة الملصق"),
        (870, 282, "إدخال المكونات يدويًا"),
        (1170, 282, "عرض نتيجة السلامة"),
    ]
    reports = [
        (270, 458, "إنشاء بلاغ"),
        (570, 458, "متابعة بلاغاتي"),
        (870, 458, "قراءة الإشعارات"),
        (1170, 458, "مراجعة كل البلاغات"),
        (270, 552, "تغيير حالة البلاغ"),
        (570, 552, "إسناد مفتش"),
        (870, 552, "لوحة الرقابة والخريطة"),
        (1170, 552, "تصدير البلاغات"),
    ]
    admin = [
        (270, 726, "إدارة المواد المحظورة"),
        (570, 726, "التصنيف المحلي الليبي"),
        (870, 726, "مزامنة المرجع"),
        (1170, 726, "مراجعة غير المطابق"),
        (270, 814, "تعديل ودمج وتعطيل منشأة"),
        (570, 814, "إدارة المستخدمين"),
        (870, 814, "سجل التدقيق"),
    ]
    for x, y, label in public:
        _oval(b, x, y, ow, oh, label, TEAL)
    for x, y, label in reports:
        _oval(b, x, y, ow, oh, label, CLAY)
    for x, y, label in admin:
        _oval(b, x, y, ow, oh, label, NAVY)

    actors = [
        (100, 200, "زائر غير مسجّل", 250),
        (100, 430, "مستهلك", 530),
        (1600, 180, "مفتش", 500),
        (1600, 340, "ضابط حرس بلدي", 500),
        (1600, 500, "أخصائي سلامة", 500),
        (1600, 680, "مدير النظام", 760),
    ]
    for x, y, name, target_y in actors:
        b.actor(x, y, name)
        start = (x + 28, y + 36) if x < 400 else (x - 28, y + 36)
        end_x = 240 if x < 400 else 1460
        b.line(start, (end_x, target_y), TEAL if x < 400 else CLAY, 2)
    b.line((128, 466), (240, 300), TEAL, 2)
    b.line((1572, 216), (1460, 790), CLAY, 2)

    b.round((40, 960, 1620, 140), 12, WHITE, NAVY, 2)
    b.text((56, 972), "قراءة الارتباط", b.bold, NAVY)
    notes = [
        "الزائر يصل إلى مجموعة التحقق فقط، بلا بلاغ. المستهلك يصل إلى التحقق وإلى إنشاء البلاغ ومتابعته والإشعارات.",
        "تأكيد قراءة الملصق امتداد لفحص الصورة إذا كانت الثقة أقل من 0.65. كل فحص يتضمن عرض نتيجة السلامة، والثقة لا تغيّر القرار.",
        "ضابط الحرس والأخصائي والمفتش والمدير يصلون إلى مجموعة البلاغ. تغيير الحالة والإسناد للمفتش والضابط والمدير، لا للأخصائي.",
        "إدارة المواد والمرجع والمنشآت للمفتش والمدير. المستخدمون وسجل التدقيق للمدير وحده. التسجيل الذاتي لا يمنح دورًا رقابيًا.",
    ]
    yy = 998
    for note in notes:
        b.text((56, yy), "• " + note, b.small, INK)
        yy += 22
    b.save("usecase.png")


def klass_diagram():
    b = Board(1960, 1680, "مخطط الأصناف", "الأسهم للعلاقات المتجاورة فقط، وبقية المفاتيح في جدول أسفل المخطط")
    packages = [
        (24, 74, 1912, 210, "الحسابات والمتابعة", SOFT),
        (24, 296, 1912, 360, "المنتج والفحص", "#F8F1E4"),
        (24, 668, 1912, 360, "المكوّن والمرجع المعياري", "#F3F7F2"),
        (24, 1040, 1912, 230, "المنشأة والبلاغ", WARN),
    ]
    for x, y, w, h, title, fill in packages:
        b.round((x, y, w, h), 12, fill, "#C9D3D8", 2)
        b.text((x + 16, y + 8), title, b.bold, NAVY)

    def link(left, right, label):
        b.arrow(left, right, LINE, 2)
        mx = (left[0] + right[0]) / 2
        my = min(left[1], right[1]) - 14
        if label:
            b.text((mx, my), label, b.tiny, CLAY, anchor='mm')

    N = b.klass(48, 118, 230, 'Notification', ['type', 'title / body', 'entity type / id', 'is_read'])
    U = b.klass(360, 118, 250, 'User', ['UUID', 'username', 'full_name / phone', 'role', 'language', 'is_active'])
    A = b.klass(690, 118, 250, 'AuditLog', ['action', 'entity type / id', 'old_value', 'new_value', 'ip / device'])
    b.klass(1020, 118, 280, 'SafetyRule', ['rule_name', 'condition JSON', 'resulting_status', 'weight', 'is_active'], '«غير مستدعى في الفحص»')
    b.round((1340, 118, 560, 140), 8, WHITE, TEAL, 2)
    b.text((1356, 130), 'خدمات بلا جدول', b.bold, TEAL)
    b.text((1356, 156), 'engine يجمّع حالة المنتج', b.small)
    b.text((1356, 178), 'matching يطابق النص', b.small)
    b.text((1356, 200), 'services يحل اختصاص LY', b.small)
    b.text((1356, 222), 'ocr يقرأ الملصق ولا يقرر', b.small)
    link(U['left'], N['right'], '1 — *')
    link(U['right'], A['left'], '1 — *')

    BR = b.klass(48, 348, 210, 'Brand', ['name_ar / name_en', 'country'])
    P = b.klass(320, 348, 230, 'Product', ['barcode فريد', 'name_ar / name_en', 'brand', 'expiry_date'])
    PI = b.klass(610, 348, 250, 'ProductIngredient', ['product', 'ingredient', 'position', 'MANUAL أو OCR'])
    ING = b.klass(920, 348, 250, 'Ingredient', ['e_number / CAS', 'safety_status', 'risk_level', 'data_origin'])
    PS = b.klass(48, 520, 250, 'ProductScan', ['user / product', 'scan_method', 'store', 'lat / lng', 'consent'])
    SA = b.klass(360, 520, 250, 'SafetyAssessment', ['scan واحد', 'product_status', 'results JSON', 'summary'])
    SI = b.klass(680, 520, 210, 'ScanImage', ['scan', 'image', 'image_type'])
    OC = b.klass(950, 520, 240, 'OCRResult', ['صورة واحدة', 'raw_text', 'confidence', 'time_ms'])
    link(BR['right'], P['left'], '1 — *')
    link(P['right'], PI['left'], '1 — *')
    link(PI['right'], ING['left'], '* — 1')
    link(PS['right'], SA['left'], '1 — 1')
    link(SI['right'], OC['left'], '1 — 1')

    RS = b.klass(48, 720, 230, 'ReferenceSource', ['code فريد', 'name_ar / en', 'is_active'])
    RA = b.klass(340, 720, 250, 'ReferenceAdditive', ['E / INS / CAS', 'names', 'primary_source', 'external_id'])
    SYN = b.klass(650, 720, 230, 'ReferenceSynonym', ['additive', 'synonym', 'language'])
    RR = b.klass(940, 720, 240, 'StatusRecord', ['additive / source', 'jurisdiction', 'status', 'effective_date'])
    LO = b.klass(1240, 720, 240, 'LocalOverride', ['additive', 'jurisdiction', 'status', 'is_active'])
    AL = b.klass(48, 890, 230, 'IngredientAlias', ['ingredient', 'alias', 'language'])
    ISO = b.klass(330, 890, 240, 'IngredientSource', ['ingredient', 'source_name', 'document'])
    UQ = b.klass(620, 890, 230, 'UnmatchedQuery', ['query_text', 'hit_count', 'resolved'])
    b.klass(900, 890, 270, 'ReferenceSyncLog', ['IMPORT أو SYNC', 'read / created', 'updated / skipped', 'success'])
    link(RS['right'], RA['left'], '1 — *')
    link(RA['right'], SYN['left'], '1 — *')

    ST = b.klass(48, 1096, 250, 'Store', ['name', 'type / city', 'lat / lng', 'status', 'merged_into'])
    b.klass(360, 1096, 260, 'MunicipalAuthority', ['name / city', 'phone / email', 'bbox lat lng'])
    CA = b.klass(680, 1096, 230, 'Attachment', ['complaint', 'file', 'IMAGE أو DOCUMENT'])
    C = b.klass(980, 1096, 270, 'Complaint', ['reporter', 'product / scan', 'store / authority', 'status / severity'])
    CH = b.klass(1320, 1096, 270, 'StatusHistory', ['complaint', 'old / new', 'changed_by', 'notes'])
    link(C['left'], CA['right'], '1 — *')
    link(C['right'], CH['left'], '1 — *')
    b.text((60, 1072), 'دمج المنشأة: Store * — 0..1 Store', b.tiny, CLAY)

    b.round((24, 1288, 1912, 360), 12, WHITE, NAVY, 2)
    b.text((40, 1304), 'كل علاقات المفاتيح الأجنبية', b.bold, NAVY)
    rows = [
        'User 1—* Notification ، و 1—* AuditLog ، و 1—* Complaint كمبلّغ ، و 0..1 مفتش مسنَد على البلاغ.',
        'User 1—* SafetyRule.created_by. مسار الفحص الحالي لا يقرأ هذا الجدول.',
        'Brand 1—* Product. Product 1—* ProductIngredient *—1 Ingredient. الزوج (منتج، مكوّن) فريد.',
        'Product 1—* ProductScan وهو اختياري على الفحص. ProductScan 1—* ScanImage و 1—1 SafetyAssessment.',
        'ScanImage 1—1 OCRResult. ProductScan *—0..1 User و *—0..1 Store.',
        'Complaint *—0..1 Product و ProductScan و Store و MunicipalAuthority.',
        'Ingredient *—0..1 ReferenceAdditive ، و 1—* Alias و Source و Classification.',
        'ReferenceSource 1—* ReferenceAdditive و 1—* StatusRecord. حذف المصدر ممنوع ما دام مستخدمًا.',
        'ReferenceAdditive 1—* Synonym و 1—* StatusRecord و 1—* LocalOverride. تجاوز واحد لكل مادة واختصاص.',
        'UnmatchedQuery بلا مفتاح أجنبي. ReferenceSyncLog *—0..1 Source و *—0..1 User.',
        'Store *—0..1 Store عبر merged_into. Complaint 1—* Attachment و 1—* StatusHistory.',
        'الحذف المتسلسل للتوابع. SET NULL عند حذف المنتج أو الفحص أو المنشأة المرتبطة اختياريًا.',
    ]
    yy = 1336
    for row in rows:
        b.text((40, yy), '• ' + row, b.small, INK)
        yy += 24
    b.save('class.png')


def sequence(filename, title, actors, steps):
    n = len(actors)
    width = max(1280, 160 + n * 230)
    height = 130 + len(steps) * 46 + 40
    b = Board(width, height, title, "تسلسل مأخوذ من مسار الكود الحالي")
    xs = []
    gap = (width - 120) / n
    top = 100
    bottom = height - 24
    for i, name in enumerate(actors):
        x = 80 + gap * i + gap / 2
        xs.append(x)
        bw = min(180, gap - 24)
        b.round((x - bw / 2, 74, bw, 32), 8, NAVY, NAVY, 1)
        b.text((x, 90), name, b.small, WHITE, anchor="mm")
        b.dashed((x, top + 8), (x, bottom), "#B7C2C8", 1, 7)

    y = 124
    for src, dst, label, kind in steps:
        y1 = y
        if kind == "note":
            b.round((70, y - 8, width - 140, 30), 6, GOLD, "#E2C98A", 1)
            b.text((86, y + 6), label, b.small, INK)
        else:
            x1, x2 = xs[src], xs[dst]
            if src == dst:
                b.line((x1, y1), (x1 + 70, y1), LINE, 2)
                b.line((x1 + 70, y1), (x1 + 70, y1 + 16), LINE, 2)
                b.arrow((x1 + 70, y1 + 16), (x1, y1 + 16), LINE, 2)
                b.text((x1 + 76, y1 - 2), label, b.tiny, INK)
            else:
                if kind == "return":
                    b.dashed((x1, y1), (x2, y1), TEAL, 2, 6)
                    b.arrow((x1, y1), (x2, y1), TEAL, 2)
                else:
                    b.arrow((x1, y1), (x2, y1), LINE, 2)
                mid = (x1 + x2) / 2
                b.text((mid, y1 - 16), label, b.tiny, INK if kind != "return" else TEAL, anchor="mt")
        y += 46
    b.save(filename)


def sequences():
    sequence(
        "seq_01_login.png",
        "1. تسجيل الدخول",
        ["المستخدم", "صفحة الدخول", "Django Auth", "الجلسة"],
        [
            (0, 1, "يفتح /accounts/login/", "call"),
            (1, 0, "نموذج اسم المستخدم وكلمة المرور", "return"),
            (0, 1, "يرسل البيانات", "call"),
            (1, 2, "LoginView يتحقق من الهوية", "call"),
            (2, 2, "نجاح: إنشاء جلسة", "call"),
            (2, 3, "يحفظ معرّف المستخدم", "call"),
            (1, 0, "توجيه إلى الصفحة الرئيسية", "return"),
            (3, 3, "فشل التحقق يبقي المستخدم على النموذج", "note"),
        ],
    )
    sequence(
        "seq_02_barcode.png",
        "2. الفحص بالباركود",
        ["المستخدم", "scan_barcode", "Product", "محرك السلامة", "SafetyAssessment"],
        [
            (0, 1, "يرسل رقم الباركود واختياريًا المنشأة والموقع", "call"),
            (1, 2, "بحث barcode الفريد", "call"),
            (1, 1, "ينشئ ProductScan بطريقة BARCODE", "call"),
            (4, 4, "إن لم يوجد منتج: صفحة عدم العثور والفحص يبقى بلا تقييم", "note"),
            (1, 3, "assess_product لمكوّنات المنتج", "call"),
            (3, 3, "مطابقة كل مكوّن ثم أعلى أولوية", "call"),
            (3, 1, "product_status والنتائج والملخص", "return"),
            (1, 4, "يحفظ تقييمًا واحدًا للفحص", "call"),
            (1, 0, "إشعار scan_result ثم صفحة النتيجة", "return"),
        ],
    )
    sequence(
        "seq_03_ocr.png",
        "3. الفحص بصورة الملصق",
        ["المستخدم", "scan_image", "OCR", "بوابة الثقة", "محرك السلامة"],
        [
            (0, 1, "يرفع صورة قائمة المكونات", "call"),
            (1, 1, "ProductScan بطريقة IMAGE ثم ScanImage", "call"),
            (1, 2, "معالجة الصورة ثم Tesseract وإلا RapidOCR", "call"),
            (2, 2, "قص من كلمة المكونات وتقطيع الرموز", "call"),
            (2, 3, "overall_confidence وقائمة العناصر", "return"),
            (3, 3, "أقل من 0.50 أو بين 0.50 و0.65 يحتاج تأكيدًا", "call"),
            (4, 4, "لا عناصر: صفحة فشل مع إدخال يدوي", "note"),
            (3, 0, "يوجد ما يحتاج تأكيدًا: صفحة التحقق", "return"),
            (3, 4, "وإلا تقييم النصوص المقبولة فقط", "call"),
            (1, 0, "حفظ OCRResult والتقييم ثم النتيجة", "return"),
        ],
    )
    sequence(
        "seq_04_confirm_ocr.png",
        "4. تأكيد قراءة الملصق",
        ["المستخدم", "confirm_ocr", "الجلسة", "محرك السلامة", "SafetyAssessment"],
        [
            (0, 1, "يعلّم كل سطر بقبول أو رفض", "call"),
            (1, 1, "يتحقق أن الفحص له أو لجلسته أو لطاقم", "call"),
            (1, 2, "يقرأ ocr_pending المخزّن للفحص", "call"),
            (2, 1, "قائمة العناصر وثقتها", "return"),
            (4, 4, "إعادة الالتقاط تعيد المستخدم إلى صفحة الصورة", "note"),
            (1, 3, "assess_ingredient_texts للعناصر المقبولة", "call"),
            (3, 1, "حالة المنتج دون استخدام الثقة في القرار", "return"),
            (1, 4, "ينشئ SafetyAssessment", "call"),
            (1, 2, "يحذف قائمة الانتظار من الجلسة", "call"),
            (1, 0, "صفحة النتيجة وإشعار إن كان داخلًا", "return"),
        ],
    )
    sequence(
        "seq_05_manual.png",
        "5. إدخال المكونات يدويًا",
        ["المستخدم", "scan_manual", "تقطيع النص", "محرك السلامة", "SafetyAssessment"],
        [
            (0, 1, "يرسل نص المكونات واسم المنتج اختياريًا", "call"),
            (1, 2, "tokenize_ingredients بلا صورة", "call"),
            (2, 1, "كل رمز بثقة 1.0 ومن دون تأكيد", "return"),
            (1, 1, "ProductScan بطريقة TEXT", "call"),
            (1, 3, "تقييم النصوص", "call"),
            (3, 1, "الحالة والملخص", "return"),
            (1, 4, "حفظ التقييم", "call"),
            (1, 0, "صفحة النتيجة", "return"),
        ],
    )
    sequence(
        "seq_06_search.png",
        "6. البحث ثم فحص منتج",
        ["المستخدم", "search_product", "Product", "check_product", "محرك السلامة"],
        [
            (0, 1, "نص البحث", "call"),
            (1, 2, "اسم، باركود، علامة، رقم E، اسم مكوّن", "call"),
            (2, 1, "حتى 50 منتجًا", "return"),
            (1, 0, "يعرض النتائج", "return"),
            (0, 3, "يختار منتجًا", "call"),
            (3, 2, "يحمّل المنتج ومكوّناته", "call"),
            (3, 3, "ProductScan بطريقة SEARCH", "call"),
            (3, 4, "assess_product", "call"),
            (4, 3, "نتيجة مجمّعة", "return"),
            (3, 0, "حفظ التقييم والانتقال إلى النتيجة", "return"),
        ],
    )
    sequence(
        "seq_07_complaint.png",
        "7. إنشاء بلاغ",
        ["مستخدم داخل", "create_complaint", "Store", "الشدة", "إشعار"],
        [
            (0, 1, "يفتح البلاغ من فحص قائم", "call"),
            (1, 1, "يربط فحص الضيف بالحساب إن لزم", "call"),
            (0, 1, "منشأة قائمة أو بيانات منشأة جديدة", "call"),
            (1, 2, "عند الجديد: Store بحالة NEW", "call"),
            (2, 1, "المنشأة المنشأة", "return"),
            (1, 3, "حالة الفحص وعدد غير الآمن والبلاغات السابقة", "call"),
            (3, 1, "severity_score وseverity_level", "return"),
            (1, 1, "يختار الجهة من الإحداثيات أو المدينة", "call"),
            (1, 1, "يحفظ البلاغ وتاريخ الحالة NEW", "call"),
            (1, 4, "إشعار المبلّغ والمدير والحرس والمفتشين", "call"),
            (1, 0, "صفحة تفاصيل البلاغ", "return"),
        ],
    )
    sequence(
        "seq_08_status.png",
        "8. تغيير حالة البلاغ وإسناد مفتش",
        ["مدير البلاغ", "update_status", "Complaint", "StatusHistory", "إشعار"],
        [
            (0, 1, "حالة جديدة ومفتش اختياري وملاحظة", "call"),
            (1, 1, "يتحقق من can_manage_complaints", "call"),
            (1, 2, "يقرأ الحالة الحالية", "call"),
            (4, 4, "إن أُسند مفتش والحالة ما زالت NEW تصبح ASSIGNED", "note"),
            (1, 2, "يحفظ الحالة والمفتش", "call"),
            (1, 3, "old_status وnew_status وchanged_by", "call"),
            (1, 1, "AuditLog: complaint.status_change", "call"),
            (1, 4, "complaint_update للمبلّغ", "call"),
            (1, 4, "complaint_assigned للمفتش إن وُجد", "call"),
            (1, 0, "يعود إلى تفاصيل البلاغ", "return"),
        ],
    )
    sequence(
        "seq_09_safety.png",
        "9. المطابقة وقرار السلامة",
        ["المحرك", "المرجع", "المحلي", "حل LY", "التجميع"],
        [
            (0, 1, "E ثم INS ثم CAS ثم مرادف ثم اسم ثم تقريبي ≥ 80", "call"),
            (1, 0, "تطابق مرجعي أو لا شيء", "return"),
            (0, 2, "إن فشل المرجع: E وCAS وبديل واسم وتقريبي", "call"),
            (2, 0, "تطابق محلي أو لا شيء", "return"),
            (4, 4, "الفشل يسجّل UnmatchedQuery ويزيد العداد", "note"),
            (0, 3, "تجاوز LY ثم سجل LY ثم مادة محلية ثم معلومة مرجعية", "call"),
            (3, 0, "حالة نافذة وطبقة القرار", "return"),
            (0, 4, "كل نتائج المكوّنات", "call"),
            (4, 4, "يستبعد كلمات المخزن غير المعروفة ويأخذ الأعلى أولوية", "call"),
            (4, 0, "SAFE أو WARNING أو UNSAFE أو UNKNOWN أو PENDING", "return"),
        ],
    )
    sequence(
        "seq_10_override.png",
        "10. حفظ التصنيف المحلي الليبي",
        ["مدير أو مفتش", "override_edit", "ReferenceAdditive", "LocalOverride", "AuditLog"],
        [
            (0, 1, "يفتح مادة مرجعية ويرسل الحالة والسبب والمصدر", "call"),
            (1, 1, "يتحقق من can_manage_ingredients", "call"),
            (1, 2, "يحمّل المادة المرجعية دون نسخ هويتها", "call"),
            (1, 3, "تجاوز واحد لاختصاص LY: إنشاء أو تحديث", "call"),
            (3, 3, "يحفظ status وreason وeffective_date وis_active", "call"),
            (1, 4, "override.create أو override.update مع القديم والجديد", "call"),
            (4, 4, "مزامنة المرجع لا تحذف هذا السجل", "note"),
            (1, 0, "يعود إلى تفاصيل المادة المرجعية", "return"),
        ],
    )


if __name__ == "__main__":
    usecase()
    klass_diagram()
    sequences()
