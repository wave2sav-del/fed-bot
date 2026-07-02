import os
import math
import requests
import feedparser
from datetime import datetime
from flask import Flask, render_template, jsonify
from dotenv import load_dotenv
from fredapi import Fred

load_dotenv()
FRED_API_KEY = os.getenv("FRED_API_KEY")
fred = Fred(api_key=FRED_API_KEY)

app = Flask(__name__)

def get_news():
    feed = feedparser.parse("https://www.federalreserve.gov/feeds/press_all.xml")
    return [{"title": e.title, "link": e.link, "date": e.published} for e in feed.entries[:8]]

def get_cpi_history():
    cpi = fred.get_series("CPIAUCSL").tail(13).ffill().bfill() 
    dates = [str(d.date()) for d in cpi.index]
    values = [round(float(v), 2) if not math.isnan(float(v)) else 0 for v in cpi.values]
    changes = [0] + [round(((values[i]-values[i-1])/values[i-1])*100, 4) for i in range(1, len(values))]
    return dates, values, changes

def get_rate_history():
    rate = fred.get_series("FEDFUNDS").tail(13)
    dates = [str(d.date()) for d in rate.index]
    values = [round(float(v), 2) for v in rate.values]
    return dates, values

def analyze(news):
    hw = ["hike", "tighten", "restrictive", "inflation", "raise"]
    dv = ["cut", "ease", "pause", "lower", "reduce", "pivot"]
    hs = ds = 0
    for n in news:
        t = n["title"].lower()
        for w in hw:
            if w in t: hs += 1
        for w in dv:
            if w in t: ds += 1
    total = hs + ds
    if total == 0: return 50, 50
    p = round((hs / total) * 100)
    return p, 100 - p

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/data")
def data():
    news = get_news()
    cpi_dates, cpi_values, cpi_changes = get_cpi_history()
    rate_dates, rate_values = get_rate_history()
    hp, dp = analyze(news)
    current_change = cpi_changes[-1]
    level = "مرتفع" if current_change > 0.2 else "منخفض" if current_change < 0 else "متعادل"
    return jsonify({
        "hawkish": hp, "dovish": dp,
        "cpi_dates": cpi_dates, "cpi_values": cpi_values, "cpi_changes": cpi_changes,
        "rate_dates": rate_dates, "rate_values": rate_values,
        "current_cpi": cpi_values[-1], "current_change": current_change,
        "inflation_level": level, "current_rate": rate_values[-1],
        "news": news, "updated": datetime.now().strftime("%Y-%m-%d %H:%M")
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
