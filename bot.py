import os
import threading
import requests
import feedparser
import schedule
import time
from datetime import datetime
from flask import Flask
from dotenv import load_dotenv
from scorer import classify_event, score_text, calculate_confidence, calculate_asset_bias
from sentiment import get_sentiment_report
from tone import get_tone_report
from data_engine import get_all_data
from fed_engine import score_indicator, analyze_fed_speech

load_dotenv()
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Fed Bot is running!"

# ==============================
# إرسال تيليغرام
# ==============================
def send_telegram(message):
    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        r = requests.post(url, data=data)
        print("ارسال:", r.status_code)
    except Exception as e:
        print("خطأ:", e)

# ==============================
# جلب أخبار الفيدرالي
# ==============================
def get_fed_news():
    feed = feedparser.parse("https://www.federalreserve.gov/feeds/press_all.xml")
    news = []
    for entry in feed.entries[:8]:
        impact, weight = classify_event(entry.title)
        news.append({
            "title":  entry.title,
            "link":   entry.link,
            "impact": impact,
            "weight": weight,
        })
    return news

# ==============================
# بناء وإرسال التقرير
# ==============================
def build_and_send():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] جاري بناء التقرير...")

    # 1. بيانات السوق
    try:
        sentiment_report, market_data, fear_score = get_sentiment_report()
        vix        = market_data["vix"]
        dxy        = market_data["dxy"]
        dxy_change = float(market_data["dxy_change"])
        us10y      = market_data["us10y"]
    except:
        vix = 20; dxy = 103; dxy_change = 0; us10y = 4.3; fear_score = 50

    # 2. نبرة الفيدرالي
    try:
        tone_report, tone_hawk, tone_dove = get_tone_report()
    except:
        tone_hawk = 50; tone_dove = 50

    # 3. البيانات الاقتصادية المحدّثة
    try:
        econ = get_all_data()
    except Exception as e:
        print("خطأ في البيانات:", e)
        econ = {}

    # 4. الأخبار
    news = get_fed_news()

    # 5. حساب النقاط من الأخبار
    hawk_total = 0
    dove_total = 0
    hawk_reasons = []
    dove_reasons = []

    for n in news:
        h, d, hr, dr = score_text(n["title"])
        multiplier   = n["weight"] / 100
        hawk_total  += h * multiplier
        dove_total  += d * multiplier
        hawk_reasons += hr
        dove_reasons += dr

    # 6. نقاط من data_engine
    scores_list = []

    cpi = econ.get("cpi", {})
    if cpi.get("actual") and cpi.get("forecast"):
        s, bias_l, conf, reason = score_indicator("CPI", cpi["actual"], cpi["forecast"])
        scores_list.append(s)
        if s > 0:
            hawk_total += abs(s)
            hawk_reasons.append(f"CPI: {reason}")
        elif s < 0:
            dove_total += abs(s)
            dove_reasons.append(f"CPI: {reason}")

    nfp = econ.get("nfp", {})
    if nfp.get("actual") and nfp.get("forecast"):
        s, bias_l, conf, reason = score_indicator("NFP", nfp["actual"], nfp["forecast"])
        scores_list.append(s)
        if s > 0:
            hawk_total += abs(s)
            hawk_reasons.append(f"NFP: {reason}")
        elif s < 0:
            dove_total += abs(s)
            dove_reasons.append(f"NFP: {reason}")

    unemp = econ.get("unemployment", {})
    if unemp.get("actual") and unemp.get("forecast"):
        s, bias_l, conf, reason = score_indicator("Unemployment", unemp["actual"], unemp["forecast"])
        scores_list.append(s)
        if s > 0:
            hawk_total += abs(s)
        elif s < 0:
            dove_total += abs(s)

    gdp = econ.get("gdp", {})
    if gdp.get("actual") and gdp.get("forecast"):
        s, bias_l, conf, reason = score_indicator("GDP", gdp["actual"], gdp["forecast"])
        scores_list.append(s)
        if s > 0:
            hawk_total += abs(s)
        elif s < 0:
            dove_total += abs(s)

    # 7. دمج نبرة التصريحات
    hawk_total += tone_hawk * 0.3
    dove_total += tone_dove * 0.3

    # 8. النسب النهائية
    total = hawk_total + dove_total
    if total == 0:
        hawk_pct = 50; dove_pct = 50
    else:
        hawk_pct = round((hawk_total / total) * 100)
        dove_pct = 100 - hawk_pct

    confidence = calculate_confidence(hawk_total, dove_total, len(news))
    bias = calculate_asset_bias(hawk_pct, dove_pct, vix, dxy_change, us10y)

    # 9. Fear label
    if fear_score >= 60:   fear_label = "طمع 🟢"
    elif fear_score >= 45: fear_label = "محايد ⚪"
    elif fear_score >= 30: fear_label = "خوف 🟡"
    else:                  fear_label = "خوف شديد 🔴"

    # 10. VIX تحليل
    if vix >= 30:   vix_label = "خوف شديد 🔴"
    elif vix >= 20: vix_label = "خوف 🟡"
    elif vix >= 15: vix_label = "محايد ⚪"
    else:           vix_label = "طمع 🟢"

    # 11. US10Y تحليل
    if us10y >= 4.8:   y10_label = "ضغط Hawkish شديد 🔴"
    elif us10y >= 4.3: y10_label = "ضغط Hawkish 🟡"
    elif us10y >= 3.8: y10_label = "محايد ⚪"
    else:              y10_label = "Dovish 🟢"

    bh = "=" * (hawk_pct // 10) + "-" * (10 - hawk_pct // 10)
    bd = "=" * (dove_pct // 10) + "-" * (10 - dove_pct // 10)

    # 12. بناء التقرير
    lines = [
        "FED DAILY REPORT",
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        "",
        "━━━━━━━━━━━━━━━━━━━━━",
        "FEAR & GREED INDEX",
        f"Score: {fear_score}/100 — {fear_label}",
        f"VIX:  {vix}  {vix_label}",
        f"DXY:  {dxy}",
        f"10Y:  {us10y}%  {y10_label}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━",
        "ECONOMIC DASHBOARD",
        "",
    ]

    # CPI
    if cpi.get("actual"):
        fc = cpi.get("forecast", "N/A")
        fresh = cpi.get("freshness", {}).get("status", "")
        diff = round(cpi["actual"] - fc, 2) if fc != "N/A" else 0
        color = "🔴" if diff > 0 else "🟢" if diff < 0 else "⚪"
        lines.append(f"{color} التضخم CPI")
        lines.append(f"   Actual: {cpi['actual']}%  |  Forecast: {fc}%")
        lines.append(f"   {'أعلى' if diff > 0 else 'أقل'} من التوقع بـ {abs(diff)} {color}  {fresh}")
        lines.append("")

    # NFP
    if nfp.get("actual"):
        fc = nfp.get("forecast")
        color = "🟢" if nfp["actual"] and fc and nfp["actual"] > fc else "🔴" if nfp["actual"] and fc and nfp["actual"] < fc else "⚪"
        lines.append(f"{color} الوظائف NFP")
        lines.append(f"   Actual: {nfp['actual']}K  |  Forecast: {fc}K")
        lines.append("")
    else:
        lines.append("⚪ الوظائف NFP")
        lines.append(f"   Actual: N/A  |  Forecast: {nfp.get('forecast', 'N/A')}K")
        lines.append("")

    # البطالة
    if unemp.get("actual"):
        fc = unemp.get("forecast", 4.2)
        diff = round(unemp["actual"] - fc, 1)
        color = "🔴" if diff > 0 else "🟢" if diff < 0 else "⚪"
        lines.append(f"{color} البطالة")
        lines.append(f"   Actual: {unemp['actual']}%  |  Forecast: {fc}%")
        lines.append("")

    # GDP
    if gdp.get("actual"):
        fc = gdp.get("forecast", 1.8)
        diff = round(gdp["actual"] - fc, 1)
        color = "🟢" if diff > 0 else "🔴" if diff < 0 else "⚪"
        lines.append(f"{color} النمو GDP")
        lines.append(f"   Actual: {gdp['actual']}%  |  Forecast: {fc}%")
        lines.append("")

    # سعر الفائدة
    rate = econ.get("fed_rate", {})
    if rate.get("actual"):
        lines.append(f"💰 سعر الفائدة الحالي: {rate['actual']}%")
        lines.append("")

    lines += [
        "━━━━━━━━━━━━━━━━━━━━━",
        "SCORING ENGINE",
        f"تشديد Hawkish: {hawk_pct}%  [{bh}]",
        f"تيسير  Dovish: {dove_pct}%  [{bd}]",
        f"Confidence: {confidence}%",
        "",
    ]

    if hawk_reasons:
        lines.append("اسباب Hawkish:")
        for r in hawk_reasons[:3]:
            lines.append(f"  + {r}")
        lines.append("")

    if dove_reasons:
        lines.append("اسباب Dovish:")
        for r in dove_reasons[:3]:
            lines.append(f"  - {r}")
        lines.append("")

    lines += [
        "━━━━━━━━━━━━━━━━━━━━━",
        "ASSET BIAS",
        f"USD:    {bias['usd']['score']:+.1f}  {bias['usd']['bias']}",
        f"Gold:   {bias['gold']['score']:+.1f}  {bias['gold']['bias']}",
        f"Nasdaq: {bias['nasdaq']['score']:+.1f}  {bias['nasdaq']['bias']}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━",
        "TOP NEWS",
    ]

    impact_icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}
    for n in news[:4]:
        icon = impact_icon.get(n["impact"], "⚪")
        lines.append(f"{icon} [{n['impact']}] {n['title'][:55]}...")

    report = "\n".join(lines)
    print(report)
    send_telegram(report)

# ==============================
# تنبيه أخبار عالية التأثير
# ==============================
last_titles = []

def check_breaking_news():
    global last_titles
    feed = feedparser.parse("https://www.federalreserve.gov/feeds/press_all.xml")
    for entry in feed.entries[:3]:
        if entry.title not in last_titles:
            impact, weight = classify_event(entry.title)
            if impact in ["CRITICAL", "HIGH"]:
                send_telegram(f"تنبيه عاجل! {impact}\n{entry.title}\n{entry.link}")
                print("تنبيه:", entry.title)
    last_titles = [e.title for e in feed.entries[:3]]

# ==============================
# الجدول الزمني
# ==============================
schedule.every().day.at("08:00").do(build_and_send)
schedule.every().day.at("16:00").do(build_and_send)
schedule.every(1).hours.do(check_breaking_news)

def run_bot():
    build_and_send()
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    print("البوت يعمل الان...")
    t = threading.Thread(target=run_bot)
    t.daemon = True
    t.start()
    port = int(os.environ.get("PORT", 5000))
    app_flask.run(host="0.0.0.0", port=port)
