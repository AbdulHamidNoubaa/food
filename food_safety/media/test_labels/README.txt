Test product labels for Food Safety OCR / Rules Engine

How to use:
1. Open /scan/ (image OCR or manual verify)
2. Upload a PNG from this folder
3. Compare result with Expected status

Files:
01_candy_unsafe_E171_E120.png     -> UNSAFE (E171, E120)  barcode 6223000000002
02_biscuit_warning_E471.png       -> WARNING (E471)       barcode 6223000000001
03_lemon_drink_safe_E330.png      -> SAFE (E330)          barcode 6223000000003
04_jelly_unsafe_E131.png          -> UNSAFE (E131)
05_snack_unsafe_E173_E175.png     -> UNSAFE (E173, E175)
06_ocr_hard_mixed_case.png        -> UNSAFE (lowercase e171/e120)
07_phone_crop_E171_E120.png       -> UNSAFE compact crop

Synthetic labels for testing only.
