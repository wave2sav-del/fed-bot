# economic_data.py — جلب البيانات الاقتصادية مع Actual vs Forecast

import requests
from fredapi import Fred
from dotenv import load_dotenv
import os

load_dotenv()
fred = Fred(api_key=os.getenv("FRED_API_KEY"))

def get_forex_factory():
    try:
        urls = [
            "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
            "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
        ]
        events = []
        for url in urls:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                events += r.json()
        return events
    except Exception as e:
        print("خطأ في Forex Factory:", e)
        return []

USD_EVENTS = {
    "cpi m/m":       {"name": "التضخم CPI",   "type": "inflation"},
    "cpi y/y":       {"name": "التضخم CPI",   "type": "inflation"},
    "core cpi":      {"name": "Core CPI",      "type": "inflation"},
    "pce":           {"name": "PCE",           "type": "inflation"},
    "non-farm":      {"name": "الوظائف NFP",   "type": "jobs"},
    "unemployment":  {"name": "البطالة",       "type": "unemployment"},
    "gdp":           {"name": "النمو GDP",     "type": "gdp"},
    "interest rate": {"name": "سعر الفائدة",  "type": "rate"},
    "fed funds":     {"name": "سعر الفائدة",  "type": "rate"},
}

def filter_usd_events(events):
    usd = []
    for e in events:
        if e.get("country") != "USD":
            continue
        title_lower = e["title"].lower()
        for key, info in USD_EVENTS.items():
            if key in title_lower:
                e["category"] = info["name"]
                e["type"]     = info["type"]
                usd.append(e)
                break
    return usd

def parse_forecast(value, event_type):
    if not value or value == "":
        return None
    try:
        clean = str(value).replace("%", "").replace("K", "").strip()
        num = float(clean)
        # البطالة لا تتجاوز 20% — إذا جاءت كبيرة تجاهلها
        if event_type == "unemployment" and num > 20:
            return None
        # الوظائف تكون بالآلاف
        if event_type == "jobs" and "K" in str(value):
            return num
        return num
    except:
        return None

def get_cpi_yoy():
    cpi = fred.get_series("CPIAUCSL").dropna().tail(13)
    cur = cpi.iloc[-1]
    yago = cpi.iloc[-13] if len(cpi) >= 13 else cpi.iloc[0]
    return round(((cur - yago) / yago) * 100, 2)

def get_unemployment():
    return round(float(fred.get_series("UNRATE").dropna().iloc[-1]), 1)

def get_gdp_growth():
    return round(float(fred.get_series("A191RL1Q225SBEA").dropna().iloc[-1]), 1)

def get_fed_rate():
    return round(float(fred.get_series("FEDFUNDS").dropna().iloc[-1]), 2)

def calculate_vs_forecast(actual, forecast, event_type):
    if actual is None or forecast is None:
        return None, "لا توجد توقعات", "⚪"

    diff = round(actual - forecast, 2)

    if event_type in ["inflation", "rate"]:
        if diff > 0:
            return -abs(diff), f"أعلى من التوقع بـ {abs(diff)} 🔴", "🔴"
        elif diff < 0:
            return abs(diff),  f"أقل من التوقع بـ {abs(diff)} 🟢", "🟢"
        else:
            return 0, "مطابق للتوقع ⚪", "⚪"
    elif event_type == "unemployment":
        if diff > 0:
            return -abs(diff), f"أعلى من التوقع بـ {abs(diff)}% 🔴", "🔴"
        elif diff < 0:
            return abs(diff),  f"أقل من التوقع بـ {abs(diff)}% 🟢", "🟢"
        else:
            return 0, "مطابق للتوقع ⚪", "⚪"
    else:
        if diff > 0:
            return abs(diff),  f"أعلى من التوقع بـ {abs(diff)} 🟢", "🟢"
        elif diff < 0:
            return -abs(diff), f"أقل من التوقع بـ {abs(diff)} 🔴", "🔴"
        else:
            return 0, "مطابق للتوقع ⚪", "⚪"

def get_economic_dashboard():
    default_data = {
        "التضخم CPI":  {"actual": get_cpi_yoy(),     "type": "inflation",    "forecast": 2.6,  "unit": "%"},
        "البطالة":     {"actual": get_unemployment(), "type": "unemployment", "forecast": 4.2,  "unit": "%"},
        "النمو GDP":   {"actual": get_gdp_growth(),   "type": "gdp",          "forecast": 1.8,  "unit": "%"},
        "الوظائف NFP": {"actual": None,               "type": "jobs",         "forecast": 185,  "unit": "K"},
        "سعر الفائدة": {"actual": get_fed_rate(),     "type": "rate",         "forecast": 4.25, "unit": "%"},
    }

    events = get_forex_factory()
    usd_events = filter_usd_events(events)
    for e in usd_events:
        cat = e.get("category")
        if cat and cat in default_data:
            parsed = parse_forecast(e.get("forecast"), e.get("type"))
            if parsed is not None:
                default_data[cat]["forecast"] = parsed

    lines = ["ECONOMIC DASHBOARD", "━━━━━━━━━━━━━━━━━━━━━", ""]
    scores = []

    for name, data in default_data.items():
        actual   = data["actual"]
        forecast = data["forecast"]
        etype    = data["type"]
        unit     = data["unit"]

        impact, label, color = calculate_vs_forecast(actual, forecast, etype)

        actual_str   = f"{actual}{unit}" if actual is not None else "N/A"
        forecast_str = f"{forecast}{unit}"

        lines.append(f"{color} {name}")
        lines.append(f"   Actual: {actual_str}  |  Forecast: {forecast_str}")
        lines.append(f"   {label}")
        lines.append("")

        if impact is not None:
            scores.append(impact)

    if scores:
        avg = round(sum(scores) / len(scores), 2)
        if avg > 0.1:
            overall = "🟢 إيجابي للسوق"
        elif avg < -0.1:
            overall = "🔴 سلبي للسوق"
        else:
            overall = "⚪ محايد"
        lines.append(f"التأثير الكلي: {overall}")

    return "\n".join(lines), default_data

if __name__ == "__main__":
    print("اختبار economic_data.py...")
    report, data = get_economic_dashboard()
    print(report)
