import os
import threading
from flask import Flask
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Fed Bot is running!"
import requests
import feedparser
import schedule
import time
from datetime import datetime
from dotenv import load_dotenv
from fredapi import Fred
from scorer import (classify_event, score_text, score_actual_vs_forecast,
                    calculate_confidence, calculate_asset_bias)
from sentiment import get_sentiment_report
from tone import get_tone_report
from economic_data import get_economic_dashboard

load_dotenv()
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FRED_API_KEY     = os.getenv("FRED_API_KEY")
fred = Fred(api_key=FRED_API_KEY)

def send_telegram(message):
    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        r = requests.post(url, data=data)
        print("ارسال:", r.status_code)
    except Exception as e:
        print("خطأ:", e)

def get_fed_news():
    feed = feedparser.parse("https://www.federalreserve.gov/feeds/press_all.xml")
    news = []
    for entry in feed.entries[:8]:
        impact, weight = classify_event(entry.title)
        news.append({
            "title":  entry.title,
            "link":   entry.link,
            "date":   entry.published,
            "impact": impact,
            "weight": weight,
        })
    return news

def get_inflation():
    cpi  = fred.get_series("CPIAUCSL").iloc[-2:]
    cur  = cpi.iloc[-1]
    prev = cpi.iloc[-2]
    ch   = round(((cur - prev) / prev) * 100, 4)
    rate = round(fred.get_series("FEDFUNDS").iloc[-1], 2)
    return {
        "cpi":    round(cur, 2),
        "change": ch,
        "level":  "مرتفع" if ch > 0.2 else "منخفض" if ch < 0 else "متعادل",
        "rate":   rate,
    }

def build_and_send():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] جاري بناء التقرير...")

    # 1. بيانات السوق
    sentiment_report, market_data, fear_score = get_sentiment_report()
    vix        = market_data["vix"]
    dxy_change = float(market_data["dxy_change"])
    us10y      = market_data["us10y"]

    # 2. نبرة الفيدرالي
    tone_report, tone_hawk, tone_dove = get_tone_report()

    # 3. الداشبورد الاقتصادي
    eco_report, eco_data = get_economic_dashboard()

    # 4. الأخبار
    news = get_fed_news()

    # 5. حساب النقاط
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

    # نقاط CPI
    cpi_data = eco_data.get("التضخم CPI", {})
    if cpi_data.get("actual") and cpi_data.get("forecast"):
        cpi_hawk, cpi_dove, cpi_reason = score_actual_vs_forecast(
            "CPI", cpi_data["actual"], cpi_data["forecast"]
        )
        hawk_total += cpi_hawk
        dove_total += cpi_dove
        if cpi_reason:
            hawk_reasons.append(cpi_reason)

    # نقاط البطالة
    unemp = eco_data.get("البطالة", {})
    if unemp.get("actual") and unemp.get("forecast"):
        u_hawk, u_dove, u_reason = score_actual_vs_forecast(
            "unemployment", unemp["actual"], unemp["forecast"]
        )
        hawk_total += u_hawk
        dove_total += u_dove
        if u_reason:
            dove_reasons.append(u_reason)

    # نقاط GDP
    gdp = eco_data.get("النمو GDP", {})
    if gdp.get("actual") and gdp.get("forecast"):
        g_hawk, g_dove, g_reason = score_actual_vs_forecast(
            "gdp", gdp["actual"], gdp["forecast"]
        )
        hawk_total += g_hawk
        dove_total += g_dove

    # دمج نبرة التصريحات
    hawk_total += tone_hawk * 0.3
    dove_total += tone_dove * 0.3

    # حساب النسب
    total = hawk_total + dove_total
    if total == 0:
        hawk_pct = 50
        dove_pct = 50
    else:
        hawk_pct = round((hawk_total / total) * 100)
        dove_pct = 100 - hawk_pct

    confidence = calculate_confidence(hawk_total, dove_total, len(news))
    bias = calculate_asset_bias(hawk_pct, dove_pct, vix, dxy_change, us10y)

    if fear_score >= 60:   fear_label = "طمع 🟢"
    elif fear_score >= 45: fear_label = "محايد ⚪"
    elif fear_score >= 30: fear_label = "خوف 🟡"
    else:                  fear_label = "خوف شديد 🔴"

    bh = "=" * (hawk_pct // 10) + "-" * (10 - hawk_pct // 10)
    bd = "=" * (dove_pct // 10) + "-" * (10 - dove_pct // 10)

    lines = [
        "FED DAILY REPORT",
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        "",
        "━━━━━━━━━━━━━━━━━━━━━",
        "FEAR & GREED INDEX",
        f"Score: {fear_score}/100 — {fear_label}",
        f"VIX:  {vix}  |  DXY: {market_data['dxy']}  |  10Y: {us10y}%",
        "",
        "━━━━━━━━━━━━━━━━━━━━━",
        eco_report,
        "",
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

last_titles = []

def check_breaking_news():
    global last_titles
    feed = feedparser.parse("https://www.federalreserve.gov/feeds/press_all.xml")
    for entry in feed.entries[:3]:
        if entry.title not in last_titles:
            impact, weight = classify_event(entry.title)
            if impact in ["CRITICAL", "HIGH"]:
                send_telegram(
                    f"تنبيه عاجل! {impact}\n{entry.title}\n{entry.link}"
                )
                print("تنبيه:", entry.title)
    last_titles = [e.title for e in feed.entries[:3]]

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