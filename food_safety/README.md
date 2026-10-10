# Food Safety Verification System — Django + SQLite3

نظام مؤسسي للتحقق من سلامة المنتجات الغذائية وفق وثيقة التصميم، مع قاعدة بيانات **SQLite3** وواجهة رقابية احترافية (RTL).

## التشغيل السريع

```bash
cd food_safety
..\venv\Scripts\activate          # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
# أو تحديث المرجع فقط دون مسح البيانات المحلية:
# python manage.py import_reference_data
python manage.py runserver
```

افتح: http://127.0.0.1:8000/

## حسابات تجريبية

| المستخدم | كلمة المرور | الدور |
|---|---|---|
| admin | admin123 | مدير |
| user | user123 | مستهلك |
| officer | officer123 | ضابط حرس بلدي |
| inspector | inspector123 | مفتش |
| specialist | specialist123 | أخصائي سلامة غذاء |

## باركودات تجريبية

- `6223000000001` — بسكويت (WARNING بسبب E471)
- `6223000000002` — حلوى ملونة (UNSAFE بسبب E171 و E120)
- `6223000000003` — مشروب ليمون (SAFE)

## الواجهة

- Design System موحّد (`static/css/design-system.css`)
- Sidebar حسب الدور (مستهلك / مفتش / حرس بلدي / أخصائي / أدمن)
- لوحة رقابية مع KPI ورسوم Chart.js وخريطة Leaflet
- صفحات: التحقق، المنتجات، القاعدة المرجعية، المواد المحظورة، البلاغات، الخريطة، سجل العمليات، المستخدمون

## نموذج البيانات التنظيمية

**Reference Database + Local Regulatory Overrides + Rules Engine**

- Codex / JECFA معلوماتية ولا تعني السماح في ليبيا تلقائيًا
- الحالة مرتبطة بـ Source + Jurisdiction + Effective Date
- `LocalRegulatoryOverride` يربط التصنيف الليبي بالسجل المرجعي دون تكرار الهوية
- المزامنة (`import_reference_data`) لا تمسح البيانات المحلية

## المنشآت الغذائية (ديناميكية)

المنشآت **لا تُدخل مسبقًا**. تُنشأ عند أول بلاغ، ثم تصبح متاحة للاختيار في البلاغات اللاحقة.

- حالات: `NEW` / `ACTIVE` / `UNDER_REVIEW` / `VERIFIED` / `INACTIVE`
- GPS أو تحديد يدوي على خريطة Leaflet
- كشف التكرار بالاسم + القرب (~50م)
- Admin/Inspector: تعديل، دمج، تعطيل


- AI فقط في مسار تحليل الملصق (OCR) — البحث/الباركود بدون AI
- محرك قواعد صريح وقابل للتفسير (لا قرار سلامة من AI)
- فصل ثقة الاستخراج عن حالة السلامة
- Seed من المواصفة الليبية 15/2025 + عيّنة مرجعية Codex/JECFA

## ملاحظة OCR

إن لم يكن Tesseract مثبتًا، استخدم **الإدخال النصي**. اختياري: `pip install pytesseract` + برنامج Tesseract للنظام.
