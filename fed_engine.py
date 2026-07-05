# fed_engine.py — محرك الفيدرالي الكامل

# ==============================
# 1. أوزان المؤشرات الاقتصادية
# ==============================
INDICATOR_WEIGHTS = {
    "cpi":                    10,
    "core cpi":               10,
    "core pce":               10,
    "pce":                    10,
    "powell":                  9,
    "press conference":        9,
    "fomc statement":          9,
    "dot plot":                9,
    "nfp":                     9,
    "non-farm payrolls":       9,
    "fomc minutes":            8,
    "unemployment":            8,
    "average hourly earnings": 8,
    "ism services":            8,
    "gdp":                     8,
    "williams":                8,
    "jefferson":               7,
    "waller":                  7,
    "ism manufacturing":       7,
    "retail sales":            7,
    "bowman":                  6,
    "daly":                    6,
    "jolts":                   6,
    "goolsbee":                5,
    "cook":                    5,
    "kugler":                  5,
    "jobless claims":          5,
    "factory orders":          3,
    "construction spending":   2,
}

# ==============================
# 2. أوزان أعضاء FOMC
# ==============================
FOMC_MEMBERS = {
    "powell":     1.0,
    "williams":   0.8,
    "jefferson":  0.7,
    "waller":     0.7,
    "bowman":     0.6,
    "daly":       0.6,
    "goolsbee":   0.5,
    "cook":       0.5,
    "kugler":     0.5,
}

# ==============================
# 3. Fed Language Engine
# ==============================
HAWKISH_PHRASES = {
    "higher for longer":               5,
    "additional firming may be needed": 5,
    "prepared to raise rates":          5,
    "no rate cuts anytime soon":        4,
    "inflation remains too high":       4,
    "inflation elevated":               4,
    "not appropriate to ease":          3,
    "above target":                     3,
    "restrictive policy":               3,
    "we are not done yet":              3,
    "remain vigilant":                  3,
    "overheating":                      3,
    "price stability is our mandate":   2,
    "strong labor market":              2,
    "labor market remains strong":      2,
}

DOVISH_PHRASES = {
    "prepared to cut":                 -5,
    "rate cuts":                       -5,
    "we are prepared to lower rates":  -5,
    "pivot":                           -4,
    "appropriate to ease":             -4,
    "economic slowdown":               -4,
    "inflation back to target":        -3,
    "inflation easing":                -3,
    "disinflation":                    -3,
    "labor market cooling":            -3,
    "labor market is slowing":         -2,
    "inflation is improving":          -2,
    "downside risks":                  -2,
    "we can afford to be patient":     -2,
    "cooling":                         -2,
}

NEUTRAL_PHRASES = {
    "data dependent":    0,
    "meeting by meeting": 0,
    "we will monitor":   0,
    "uncertain outlook": 0,
    "balanced risks":   -1,
    "watching carefully": 0,
}

# ==============================
# 4. تحليل نص التصريح
# ==============================
def analyze_fed_speech(text, speaker="unknown"):
    text_lower = text.lower()
    hawk_total = 0
    dove_total = 0
    found_phrases = []

    for phrase, score in HAWKISH_PHRASES.items():
        if phrase in text_lower:
            hawk_total += score
            found_phrases.append(f"+{score} ({phrase})")

    for phrase, score in DOVISH_PHRASES.items():
        if phrase in text_lower:
            dove_total += abs(score)
            found_phrases.append(f"{score} ({phrase})")

    for phrase, score in NEUTRAL_PHRASES.items():
        if phrase in text_lower:
            found_phrases.append(f"{score} ({phrase})")

    # وزن المتحدث
    speaker_lower = speaker.lower()
    multiplier = 1.0
    for member, weight in FOMC_MEMBERS.items():
        if member in speaker_lower:
            multiplier = weight
            break

    hawk_total = hawk_total * multiplier
    dove_total = dove_total * multiplier

    total = hawk_total + dove_total
    if total == 0:
        hawk_pct = 50
        dove_pct = 50
        confidence = 20
    else:
        hawk_pct = round((hawk_total / total) * 100)
        dove_pct = 100 - hawk_pct
        confidence = min(round((len(found_phrases) / 5) * 100), 95)

    if hawk_pct >= 75:   tone = "Hawkish قوي جداً 🔴🔴"
    elif hawk_pct >= 60: tone = "Hawkish 🔴"
    elif dove_pct >= 75: tone = "Dovish قوي جداً 🟢🟢"
    elif dove_pct >= 60: tone = "Dovish 🟢"
    else:                tone = "محايد ⚪"

    return {
        "speaker":     speaker,
        "multiplier":  multiplier,
        "hawk_pct":    hawk_pct,
        "dove_pct":    dove_pct,
        "tone":        tone,
        "confidence":  confidence,
        "phrases":     found_phrases,
        "hawk_score":  hawk_total,
        "dove_score":  dove_total,
    }

# ==============================
# 5. Scoring Engine — Actual vs Forecast
# ==============================
def score_indicator(name, actual, forecast, previous=None):
    if actual is None or forecast is None:
        return 0, "لا توجد بيانات", "Low"

    name_lower = name.lower()
    weight = 5
    for key, w in INDICATOR_WEIGHTS.items():
        if key in name_lower:
            weight = w
            break

    diff = actual - forecast
    if forecast != 0:
        surprise_pct = (diff / abs(forecast)) * 100
    else:
        surprise_pct = 0

    # تحديد الاتجاه حسب نوع المؤشر
    # التضخم والفائدة — ارتفاع = Hawkish
    if any(x in name_lower for x in ["cpi", "pce", "ppi", "inflation", "rate", "earnings"]):
        direction = 1 if diff > 0 else -1

    # البطالة والمطالبات — ارتفاع = Dovish
    elif any(x in name_lower for x in ["unemployment", "jobless", "claims"]):
        direction = -1 if diff > 0 else 1

    # الوظائف والنمو — ارتفاع = Hawkish / انخفاض = Dovish
    elif any(x in name_lower for x in ["nfp", "non-farm", "payroll", "gdp", "retail", "factory", "jolts", "ism"]):
        direction = 1 if diff > 0 else -1

    # باقي المؤشرات
    else:
        direction = 1 if diff > 0 else -1
    # حساب النقاط
    raw_score = (surprise_pct / 100) * weight * direction * -1 if any(x in name_lower for x in ["nfp", "non-farm", "payroll"]) and diff < 0 else (surprise_pct / 100) * weight * direction
    # Confidence
    abs_surprise = abs(surprise_pct)
    if abs_surprise >= 30:   confidence = "Very High"
    elif abs_surprise >= 15: confidence = "High"
    elif abs_surprise >= 5:  confidence = "Medium"
    else:                    confidence = "Low"

    # Bias
    if raw_score > 3:    bias = "Hawkish قوي 🔴"
    elif raw_score > 0:  bias = "Hawkish خفيف 🟡"
    elif raw_score == 0: bias = "محايد ⚪"
    elif raw_score > -3: bias = "Dovish خفيف 🟡"
    else:                bias = "Dovish قوي 🟢"

    reason = f"Actual {actual} vs Forecast {forecast} | Surprise: {round(surprise_pct, 1)}%"

    return round(raw_score, 2), bias, confidence, reason

# ==============================
# 6. Market Pricing — CME FedWatch
# ==============================
def score_market_pricing(hold_pct, cut_pct, hike_pct):
    score = ((hike_pct * 10) + (hold_pct * 0) + (cut_pct * -10)) / 100

    if cut_pct >= 80:    bias = "Dovish قوي جداً 🟢🟢"
    elif cut_pct >= 60:  bias = "Dovish 🟢"
    elif cut_pct >= 40:  bias = "Dovish خفيف 🟡"
    elif hike_pct >= 80: bias = "Hawkish قوي جداً 🔴🔴"
    elif hike_pct >= 60: bias = "Hawkish 🔴"
    elif hike_pct >= 40: bias = "Hawkish خفيف 🟡"
    else:                bias = "محايد ⚪"

    dominant = max(hold_pct, cut_pct, hike_pct)
    if dominant >= 70:   confidence = "High"
    elif dominant >= 50: confidence = "Medium"
    else:                confidence = "Low"

    return round(score, 2), bias, confidence

# ==============================
# 7. Asset Bias النهائي
# ==============================
def calculate_final_bias(total_score, vix=20, dxy_change=0, us10y=4.3):
    # USD
    usd = total_score * 0.3
    if dxy_change > 0.5:  usd += 0.5
    elif dxy_change < -0.5: usd -= 0.5

    # Gold — عكس الدولار + خوف
    gold = -total_score * 0.2
    if vix > 25:  gold += 1.0
    elif vix < 15: gold -= 0.5

    # Nasdaq — يكره Hawkish + يكره الخوف
    nasdaq = -total_score * 0.25
    if vix > 25:   nasdaq -= 1.0
    if us10y > 4.5: nasdaq -= 0.5

    def label(score):
        if score > 2:    return "Bullish قوي 🟢🟢"
        elif score > 0.5: return "Bullish خفيف 🟢"
        elif score > -0.5: return "محايد ⚪"
        elif score > -2:  return "Bearish خفيف 🔴"
        else:             return "Bearish قوي 🔴🔴"

    return {
        "usd":    {"score": round(usd, 1),    "bias": label(usd)},
        "gold":   {"score": round(gold, 1),   "bias": label(gold)},
        "nasdaq": {"score": round(nasdaq, 1), "bias": label(nasdaq)},
    }

# ==============================
# 8. Confidence الكلي
# ==============================
def calculate_overall_confidence(scores_list, speech_confidence=0):
    if not scores_list:
        return 30

    total = sum(abs(s) for s in scores_list)
    avg   = total / len(scores_list)

    base = min(round(avg * 10), 60)
    data_bonus = min(len(scores_list) * 5, 25)
    speech_bonus = speech_confidence // 10

    return min(base + data_bonus + speech_bonus, 95)

# ==============================
# اختبار
# ==============================
if __name__ == "__main__":
    print("اختبار fed_engine.py")
    print("━" * 40)

    # اختبار NFP
    score, bias, conf, reason = score_indicator("NFP", 57, 114)
    print(f"NFP: Score={score} | {bias} | {conf}")
    print(f"     {reason}")

    # اختبار البطالة
    score2, bias2, conf2, reason2 = score_indicator("Unemployment Rate", 4.2, 4.3)
    print(f"\nUnemployment: Score={score2} | {bias2} | {conf2}")
    print(f"              {reason2}")

    # اختبار Powell
    print("\nاختبار Fed Language Engine:")
    text = "Inflation remains elevated. We maintain restrictive policy. Higher for longer. Labor market remains strong."
    result = analyze_fed_speech(text, "Powell")
    print(f"Powell: Hawkish={result['hawk_pct']}% | Dovish={result['dove_pct']}%")
    print(f"Tone: {result['tone']} | Confidence: {result['confidence']}%")

    # اختبار Market Pricing
    print("\nاختبار Market Pricing:")
    mp_score, mp_bias, mp_conf = score_market_pricing(25, 70, 5)
    print(f"CME FedWatch: Score={mp_score} | {mp_bias} | {mp_conf}")

    # Asset Bias
    print("\nاختبار Asset Bias:")
    bias_result = calculate_final_bias(total_score=5, vix=18, dxy_change=0.3, us10y=4.4)
    for asset, data in bias_result.items():
        print(f"{asset.upper()}: {data['score']:+.1f} | {data['bias']}")
