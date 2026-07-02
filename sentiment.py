# sentiment.py — مؤشر الخوف والطمع

import yfinance as yf

# ==============================
# جلب البيانات من Yahoo Finance
# ==============================
def get_market_data():
    try:
        vix   = yf.Ticker("^VIX")
        dxy   = yf.Ticker("DX-Y.NYB")
        us10y = yf.Ticker("^TNX")

        vix_price   = vix.fast_info["lastPrice"]
        dxy_price   = dxy.fast_info["lastPrice"]
        us10y_price = us10y.fast_info["lastPrice"]

        # تغير DXY اليوم
        dxy_hist    = dxy.history(period="5d")
        dxy_change  = 0
        if len(dxy_hist) >= 2:
            dxy_change = round(dxy_hist["Close"].iloc[-1] - dxy_hist["Close"].iloc[-2], 3)

        return {
            "vix":        round(vix_price, 2),
            "dxy":        round(dxy_price, 2),
            "dxy_change": dxy_change,
            "us10y":      round(us10y_price, 2),
        }
    except Exception as e:
        print("خطأ في جلب بيانات السوق:", e)
        return {"vix": 20, "dxy": 103, "dxy_change": 0, "us10y": 4.3}

# ==============================
# تحليل VIX
# ==============================
def analyze_vix(vix):
    if vix >= 30:
        return "خوف شديد 🔴", 10
    elif vix >= 20:
        return "خوف متوسط 🟡", 35
    elif vix >= 15:
        return "محايد ⚪", 55
    else:
        return "طمع 🟢", 80

# ==============================
# تحليل DXY
# ==============================
def analyze_dxy(dxy, dxy_change):
    if dxy >= 106:
        label = "دولار قوي جداً 🔴"
    elif dxy >= 103:
        label = "دولار قوي 🟡"
    elif dxy >= 100:
        label = "دولار محايد ⚪"
    else:
        label = "دولار ضعيف 🟢"

    change_str = f"({'+' if dxy_change >= 0 else ''}{dxy_change})"
    return f"{label} {change_str}"

# ==============================
# تحليل US 10Y
# ==============================
def analyze_10y(us10y):
    if us10y >= 4.8:
        return "ضغط Hawkish شديد 🔴"
    elif us10y >= 4.3:
        return "ضغط Hawkish متوسط 🟡"
    elif us10y >= 3.8:
        return "محايد ⚪"
    else:
        return "Dovish — توقع تخفيض 🟢"

# ==============================
# حساب Fear & Greed الإجمالي
# ==============================
def calculate_fear_greed(vix, us10y, dxy):
    _, vix_score = analyze_vix(vix)

    # US 10Y — كلما ارتفع زاد الخوف
    if us10y >= 4.8:   yield_score = 15
    elif us10y >= 4.3: yield_score = 35
    elif us10y >= 3.8: yield_score = 55
    else:              yield_score = 75

    # DXY — قوة الدولار تعني ضغط على الأصول
    if dxy >= 106:   dxy_score = 20
    elif dxy >= 103: dxy_score = 40
    elif dxy >= 100: dxy_score = 60
    else:            dxy_score = 75

    # المتوسط المرجح
    score = round((vix_score * 0.5) + (yield_score * 0.3) + (dxy_score * 0.2))

    if score >= 75:   label = "طمع شديد 🟢"
    elif score >= 60: label = "طمع 🟢"
    elif score >= 45: label = "محايد ⚪"
    elif score >= 30: label = "خوف 🟡"
    else:             label = "خوف شديد 🔴"

    return score, label

# ==============================
# التقرير الكامل
# ==============================
def get_sentiment_report():
    data = get_market_data()
    vix       = data["vix"]
    dxy       = data["dxy"]
    dxy_change = data["dxy_change"]
    us10y     = data["us10y"]

    score, label = calculate_fear_greed(vix, us10y, dxy)
    vix_label    = analyze_vix(vix)[0]
    dxy_label    = analyze_dxy(dxy, dxy_change)
    yield_label  = analyze_10y(us10y)

    report = f"""
FEAR & GREED INDEX: {score}/100 — {label}
━━━━━━━━━━━━━━━━━━━━━
VIX:   {vix}    {vix_label}
DXY:   {dxy}  {dxy_label}
10Y:   {us10y}%  {yield_label}
"""
    return report, data, score

if __name__ == "__main__":
    print("اختبار sentiment.py...")
    report, data, score = get_sentiment_report()
    print(report)
    print("البيانات الخام:", data)
