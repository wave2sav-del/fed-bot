# data_engine.py — محرك البيانات المحدّثة

import requests
from datetime import datetime, timedelta
from fredapi import Fred
from dotenv import load_dotenv
import os

load_dotenv()
fred = Fred(api_key=os.getenv("FRED_API_KEY"))

# ==============================
# 1. جلب Forex Factory
# ==============================
def get_forex_factory_events():
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
        print("خطأ Forex Factory:", e)
        return []

def find_forecast(events, keyword):
    keyword_lower = keyword.lower()
    for e in events:
        if e.get("country") != "USD":
            continue
        title = e.get("title", "").lower()
        if keyword_lower in title:
            forecast = e.get("forecast", "")
            actual   = e.get("actual", "")
            previous = e.get("previous", "")
            if forecast or actual:
                return {
                    "title":    e.get("title"),
                    "forecast": forecast,
                    "actual":   actual,
                    "previous": previous,
                    "date":     e.get("date", ""),
                }
    return None

# ==============================
# 2. تحويل القيم النصية
# ==============================
def parse_value(val):
    if not val or val == "":
        return None
    try:
        clean = str(val).replace("%", "").replace("K", "").replace("B", "").replace(",", "").strip()
        num = float(clean)
        if "K" in str(val):
            num = num * 1000
        return num
    except:
        return None

# ==============================
# 3. Data Freshness
# ==============================
def check_freshness(series_id, max_days=35):
    try:
        data = fred.get_series(series_id).dropna()
        last_date = data.index[-1]
        days_old = (datetime.now() - last_date.to_pydatetime().replace(tzinfo=None)).days
        is_fresh = days_old <= max_days
        return {
            "last_date": str(last_date.date()),
            "days_old":  days_old,
            "is_fresh":  is_fresh,
            "status":    "✅ محدّث" if is_fresh else "⚠️ قديم"
        }
    except:
        return {"last_date": "N/A", "days_old": 999, "is_fresh": False, "status": "❌ خطأ"}

# ==============================
# 4. جلب CPI (نسبة سنوية)
# ==============================
def get_cpi():
    try:
        cpi = fred.get_series("CPIAUCSL").dropna().tail(14)
        current  = cpi.iloc[-1]
        year_ago = cpi.iloc[-13]
        yoy = round(((current - year_ago) / year_ago) * 100, 2)
        freshness = check_freshness("CPIAUCSL")
        return {
            "actual":    yoy,
            "raw":       round(float(current), 2),
            "freshness": freshness,
        }
    except Exception as e:
        print("خطأ CPI:", e)
        return {"actual": None, "freshness": {"status": "❌ خطأ"}}

# ==============================
# 5. جلب Core CPI
# ==============================
def get_core_cpi():
    try:
        data = fred.get_series("CPILFESL").dropna().tail(14)
        current  = data.iloc[-1]
        year_ago = data.iloc[-13]
        yoy = round(((current - year_ago) / year_ago) * 100, 2)
        return {"actual": yoy}
    except:
        return {"actual": None}

# ==============================
# 6. جلب NFP (التغير الشهري)
# ==============================
def get_nfp():
    try:
        payems = fred.get_series("PAYEMS").dropna().tail(3)
        current  = payems.iloc[-1]
        previous = payems.iloc[-2]
        change_k = round(float(current - previous), 1)
        freshness = check_freshness("PAYEMS", max_days=40)
        return {
            "actual":    change_k,
            "unit":      "K",
            "freshness": freshness,
        }
    except Exception as e:
        print("خطأ NFP:", e)
        return {"actual": None, "freshness": {"status": "❌ خطأ"}}

# ==============================
# 7. جلب البطالة
# ==============================
def get_unemployment():
    try:
        data = fred.get_series("UNRATE").dropna()
        current  = round(float(data.iloc[-1]), 1)
        previous = round(float(data.iloc[-2]), 1)
        freshness = check_freshness("UNRATE")
        return {
            "actual":    current,
            "previous":  previous,
            "freshness": freshness,
        }
    except Exception as e:
        print("خطأ البطالة:", e)
        return {"actual": None, "freshness": {"status": "❌ خطأ"}}

# ==============================
# 8. جلب متوسط الأجور
# ==============================
def get_avg_earnings():
    try:
        data = fred.get_series("CES0500000003").dropna().tail(3)
        current  = data.iloc[-1]
        previous = data.iloc[-2]
        mom = round(((current - previous) / previous) * 100, 2)
        return {"actual": mom}
    except:
        return {"actual": None}

# ==============================
# 9. جلب GDP
# ==============================
def get_gdp():
    try:
        data = fred.get_series("A191RL1Q225SBEA").dropna()
        current   = round(float(data.iloc[-1]), 1)
        freshness = check_freshness("A191RL1Q225SBEA", max_days=100)
        return {
            "actual":    current,
            "freshness": freshness,
        }
    except Exception as e:
        print("خطأ GDP:", e)
        return {"actual": None, "freshness": {"status": "❌ خطأ"}}

# ==============================
# 10. جلب سعر الفائدة الحالي
# ==============================
def get_fed_rate():
    try:
        data = fred.get_series("FEDFUNDS").dropna()
        current = round(float(data.iloc[-1]), 2)
        return {"actual": current}
    except:
        return {"actual": None}

# ==============================
# 11. تجميع كل البيانات
# ==============================
def get_all_data():
    print("جاري جلب البيانات المحدّثة...")
    events = get_forex_factory_events()
     # CPI
    cpi_data = get_cpi()
    cpi_ff   = find_forecast(events, "cpi y/y")
    cpi_forecast = 2.6
    if cpi_ff and cpi_ff.get("forecast"):
        val = parse_value(cpi_ff["forecast"])
        if val and 1.0 < val < 10.0:
            cpi_forecast = val
    # NFP
    nfp_data = get_nfp()
    nfp_ff   = find_forecast(events, "non-farm")
    nfp_forecast = parse_value(nfp_ff["forecast"]) if nfp_ff else None
    if nfp_ff and nfp_ff.get("actual"):
        nfp_actual_ff = parse_value(nfp_ff["actual"])
        if nfp_actual_ff:
            nfp_data["actual"] = nfp_actual_ff / 1000 if nfp_actual_ff > 1000 else nfp_actual_ff

   # البطالة
    unemp_data = get_unemployment()
    unemp_ff   = find_forecast(events, "unemployment rate")
    unemp_forecast_raw = parse_value(unemp_ff["forecast"]) if unemp_ff else None
    if unemp_forecast_raw and 2.0 < unemp_forecast_raw < 15.0:
        unemp_forecast = unemp_forecast_raw
    else:
        unemp_forecast = 4.2
    if unemp_ff and unemp_ff.get("actual"):
        actual_ff = parse_value(unemp_ff["actual"])
        if actual_ff and 2.0 < actual_ff < 15.0:
            unemp_data["actual"] = actual_ff
    # GDP
    gdp_data = get_gdp()
    gdp_ff   = find_forecast(events, "gdp")
    gdp_forecast = parse_value(gdp_ff["forecast"]) if gdp_ff else 1.8

    # الأجور
    earnings_data = get_avg_earnings()
    earn_ff = find_forecast(events, "average hourly earnings")
    earn_forecast = parse_value(earn_ff["forecast"]) if earn_ff else 0.3

    # سعر الفائدة
    rate_data = get_fed_rate()

    return {
        "cpi": {
            "actual":   cpi_data.get("actual"),
            "forecast": cpi_forecast,
            "freshness": cpi_data.get("freshness", {}),
            "unit": "%",
            "weight": 10,
        },
        "nfp": {
            "actual":   nfp_data.get("actual"),
            "forecast": nfp_forecast,
            "freshness": nfp_data.get("freshness", {}),
            "unit": "K",
            "weight": 9,
        },
        "unemployment": {
            "actual":   unemp_data.get("actual"),
            "forecast": unemp_forecast,
            "freshness": unemp_data.get("freshness", {}),
            "unit": "%",
            "weight": 8,
        },
        "avg_earnings": {
            "actual":   earnings_data.get("actual"),
            "forecast": earn_forecast,
            "unit": "%",
            "weight": 8,
        },
        "gdp": {
            "actual":   gdp_data.get("actual"),
            "forecast": gdp_forecast,
            "freshness": gdp_data.get("freshness", {}),
            "unit": "%",
            "weight": 8,
        },
        "fed_rate": {
            "actual": rate_data.get("actual"),
            "unit": "%",
        },
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

# ==============================
# اختبار
# ==============================
if __name__ == "__main__":
    print("اختبار data_engine.py")
    print("━" * 40)
    data = get_all_data()
    for key, val in data.items():
        if key == "updated":
            print(f"\nآخر تحديث: {val}")
        else:
            actual   = val.get("actual", "N/A")
            forecast = val.get("forecast", "N/A")
            fresh    = val.get("freshness", {}).get("status", "")
            print(f"{key}: Actual={actual} | Forecast={forecast} | {fresh}")
