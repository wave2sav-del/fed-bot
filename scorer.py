# scorer.py — محرك النقاط الرئيسي

# ==============================
# أوزان الأحداث الاقتصادية
# ==============================
EVENT_WEIGHTS = {
    # CRITICAL — وزن 100%
    "fomc rate decision":     {"weight": 100, "impact": "CRITICAL"},
    "interest rate decision":  {"weight": 100, "impact": "CRITICAL"},
    "powell":                  {"weight": 100, "impact": "CRITICAL"},
    "press conference":        {"weight": 100, "impact": "CRITICAL"},
    "cpi":                     {"weight": 100, "impact": "CRITICAL"},
    "core cpi":                {"weight": 100, "impact": "CRITICAL"},
    "pce":                     {"weight": 90,  "impact": "CRITICAL"},
    "core pce":                {"weight": 90,  "impact": "CRITICAL"},

    # HIGH — وزن 60%
    "non-farm payrolls":       {"weight": 60, "impact": "HIGH"},
    "nfp":                     {"weight": 60, "impact": "HIGH"},
    "unemployment":            {"weight": 60, "impact": "HIGH"},
    "gdp":                     {"weight": 60, "impact": "HIGH"},
    "ppi":                     {"weight": 55, "impact": "HIGH"},
    "retail sales":            {"weight": 55, "impact": "HIGH"},

    # MEDIUM — وزن 30%
    "jobless claims":          {"weight": 30, "impact": "MEDIUM"},
    "ism":                     {"weight": 30, "impact": "MEDIUM"},
    "consumer confidence":     {"weight": 30, "impact": "MEDIUM"},
    "fed speaks":              {"weight": 25, "impact": "MEDIUM"},
    "member speaks":           {"weight": 25, "impact": "MEDIUM"},

    # LOW — وزن 10%
    "stress test":             {"weight": 10, "impact": "LOW"},
    "enforcement":             {"weight": 5,  "impact": "LOW"},
    "bank":                    {"weight": 10, "impact": "LOW"},
}

# ==============================
# كلمات النبرة Hawkish / Dovish
# ==============================
HAWKISH_WORDS = {
    "restrictive":        30,
    "higher for longer":  30,
    "inflation":          20,
    "hike":               25,
    "tighten":            25,
    "raise rates":        25,
    "above target":       20,
    "persistent":         15,
    "overheating":        20,
    "strong labor":       15,
}

DOVISH_WORDS = {
    "cut":                25,
    "ease":               20,
    "pause":              20,
    "lower":              20,
    "reduce":             20,
    "pivot":              30,
    "cooling":            15,
    "slowdown":           15,
    "below target":       20,
    "weak":               15,
    "unemployment rising": 20,
}

# ==============================
# تصنيف الخبر بناءً على عنوانه
# ==============================
def classify_event(title):
    title_lower = title.lower()
    for event, info in EVENT_WEIGHTS.items():
        if event in title_lower:
            return info["impact"], info["weight"]
    return "LOW", 5

# ==============================
# حساب نقاط Hawkish/Dovish من النص
# ==============================
def score_text(text):
    text_lower = text.lower()
    hawk_score = 0
    dove_score = 0
    hawk_reasons = []
    dove_reasons = []

    for word, points in HAWKISH_WORDS.items():
        if word in text_lower:
            hawk_score += points
            hawk_reasons.append(f"{word} +{points}")

    for word, points in DOVISH_WORDS.items():
        if word in text_lower:
            dove_score += points
            dove_reasons.append(f"{word} +{points}")

    return hawk_score, dove_score, hawk_reasons, dove_reasons

# ==============================
# حساب Actual vs Forecast
# ==============================
def score_actual_vs_forecast(event_name, actual, forecast):
    if actual is None or forecast is None:
        return 0, 0, "لا توجد بيانات كافية"

    diff = actual - forecast
    event_lower = event_name.lower()
    hawk = 0
    dove = 0
    reason = ""

    # CPI / PCE / PPI — ارتفاع = Hawkish
    if any(x in event_lower for x in ["cpi", "pce", "ppi", "inflation"]):
        if diff > 0:
            hawk = round(diff * 30)
            reason = f"Actual {actual}% > Forecast {forecast}% = صدمة تضخم Hawkish"
        elif diff < 0:
            dove = round(abs(diff) * 30)
            reason = f"Actual {actual}% < Forecast {forecast}% = تضخم أقل Dovish"

    # NFP / Employment — ارتفاع = Hawkish
    elif any(x in event_lower for x in ["nfp", "payroll", "employment"]):
        if diff > 0:
            hawk = round((diff / 50) * 20)
            reason = f"Actual {actual}K > Forecast {forecast}K = سوق عمل قوي Hawkish"
        elif diff < 0:
            dove = round((abs(diff) / 50) * 20)
            reason = f"Actual {actual}K < Forecast {forecast}K = سوق عمل ضعيف Dovish"

    # Unemployment — ارتفاع = Dovish
    elif "unemployment" in event_lower:
        if diff > 0:
            dove = round(diff * 25)
            reason = f"Actual {actual}% > Forecast {forecast}% = بطالة أعلى Dovish"
        elif diff < 0:
            hawk = round(abs(diff) * 25)
            reason = f"Actual {actual}% < Forecast {forecast}% = بطالة أقل Hawkish"

    return hawk, dove, reason

# ==============================
# حساب نسبة الثقة Confidence
# ==============================
def calculate_confidence(hawk_total, dove_total, data_points):
    total = hawk_total + dove_total
    if total == 0:
        return 30

    # كلما زادت نقاط الفرق زادت الثقة
    diff_ratio = abs(hawk_total - dove_total) / total
    base_confidence = round(diff_ratio * 100)

    # كلما زادت البيانات زادت الثقة
    data_bonus = min(data_points * 5, 20)

    confidence = min(base_confidence + data_bonus, 95)
    return max(confidence, 25)

# ==============================
# حساب Asset Bias
# ==============================
def calculate_asset_bias(hawk_pct, dove_pct, vix, dxy_change, yield_10y):
    # نقطة البداية من Hawkish/Dovish
    fed_score = (hawk_pct - dove_pct) / 100  # من -1 إلى +1

    # USD
    usd_score = round(fed_score * 3, 1)
    if dxy_change > 0.5:
        usd_score += 0.5
    elif dxy_change < -0.5:
        usd_score -= 0.5

    # Gold — عكس الدولار + خوف
    gold_score = round(-fed_score * 2, 1)
    if vix > 25:
        gold_score += 1.0  # خوف يرفع الذهب
    elif vix < 15:
        gold_score -= 0.5

    # Nasdaq — يكره Hawkish + يكره الخوف
    nasdaq_score = round(-fed_score * 2.5, 1)
    if vix > 25:
        nasdaq_score -= 1.0
    if yield_10y > 4.5:
        nasdaq_score -= 0.5

    def bias_label(score):
        if score > 1.5:   return "Bullish قوي 🟢"
        elif score > 0.5: return "Bullish خفيف 🟢"
        elif score > -0.5: return "محايد ⚪"
        elif score > -1.5: return "Bearish خفيف 🔴"
        else:              return "Bearish قوي 🔴"

    return {
        "usd":    {"score": usd_score,    "bias": bias_label(usd_score)},
        "gold":   {"score": gold_score,   "bias": bias_label(gold_score)},
        "nasdaq": {"score": nasdaq_score, "bias": bias_label(nasdaq_score)},
    }

if __name__ == "__main__":
    print("اختبار scorer.py")
    impact, weight = classify_event("CPI Report Higher Than Expected")
    print(f"تصنيف الخبر: {impact} | الوزن: {weight}")
    hawk, dove, reason = score_actual_vs_forecast("CPI", 3.4, 3.1)
    print(f"Hawkish: {hawk} | Dovish: {dove}")
    print(f"السبب: {reason}")
    conf = calculate_confidence(70, 30, 5)
    print(f"الثقة: {conf}%")
    bias = calculate_asset_bias(70, 30, 22, 0.3, 4.4)
    print(f"Asset Bias: {bias}")
