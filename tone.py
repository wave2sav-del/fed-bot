# tone.py — تحليل نبرة تصريحات الفيدرالي

import feedparser
import requests
from bs4 import BeautifulSoup
from scorer import HAWKISH_WORDS, DOVISH_WORDS

# ==============================
# جلب آخر تصريحات الفيدرالي
# ==============================
def get_fed_speeches():
    speeches = []
    try:
        feed = feedparser.parse("https://www.federalreserve.gov/feeds/speeches.xml")
        for entry in feed.entries[:5]:
            speeches.append({
                "title": entry.title,
                "date":  entry.published,
                "link":  entry.link,
                "text":  entry.title  # نستخدم العنوان إذا لم نستطع قراءة النص
            })
    except Exception as e:
        print("خطأ في جلب التصريحات:", e)
    return speeches

# ==============================
# قراءة نص التصريح من الموقع
# ==============================
def fetch_speech_text(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "lxml")
        paragraphs = soup.find_all("p")
        text = " ".join([p.get_text() for p in paragraphs[:20]])
        return text
    except:
        return ""

# ==============================
# تحليل نبرة النص
# ==============================
def analyze_tone(text):
    text_lower = text.lower()
    hawk_score = 0
    dove_score = 0
    hawk_reasons = []
    dove_reasons = []

    for word, points in HAWKISH_WORDS.items():
        count = text_lower.count(word)
        if count > 0:
            total = points * min(count, 3)  # نحد التكرار بـ 3
            hawk_score += total
            hawk_reasons.append(f'"{word}" x{count} +{total}')

    for word, points in DOVISH_WORDS.items():
        count = text_lower.count(word)
        if count > 0:
            total = points * min(count, 3)
            dove_score += total
            dove_reasons.append(f'"{word}" x{count} +{total}')

    total = hawk_score + dove_score
    if total == 0:
        hawk_pct = 50
        dove_pct = 50
        tone = "محايد ⚪"
    else:
        hawk_pct = round((hawk_score / total) * 100)
        dove_pct = 100 - hawk_pct
        if hawk_pct >= 70:
            tone = "Hawkish قوي 🔴"
        elif hawk_pct >= 55:
            tone = "Hawkish خفيف 🟡"
        elif dove_pct >= 70:
            tone = "Dovish قوي 🟢"
        elif dove_pct >= 55:
            tone = "Dovish خفيف 🟡"
        else:
            tone = "محايد ⚪"

    return {
        "hawk_score":   hawk_score,
        "dove_score":   dove_score,
        "hawk_pct":     hawk_pct,
        "dove_pct":     dove_pct,
        "tone":         tone,
        "hawk_reasons": hawk_reasons,
        "dove_reasons": dove_reasons,
    }

# ==============================
# التقرير الكامل للنبرة
# ==============================
def get_tone_report():
    speeches = get_fed_speeches()

    if not speeches:
        return "لا توجد تصريحات حديثة", 50, 50

    all_hawk = 0
    all_dove = 0
    results  = []

    for speech in speeches[:3]:
        text = fetch_speech_text(speech["link"])
        if not text:
            text = speech["title"]

        analysis = analyze_tone(text)
        all_hawk += analysis["hawk_score"]
        all_dove += analysis["dove_score"]

        results.append({
            "title": speech["title"],
            "tone":  analysis["tone"],
            "hawk":  analysis["hawk_pct"],
            "dove":  analysis["dove_pct"],
        })

    total = all_hawk + all_dove
    if total == 0:
        final_hawk = 50
        final_dove = 50
    else:
        final_hawk = round((all_hawk / total) * 100)
        final_dove = 100 - final_hawk

    if final_hawk >= 70:   final_tone = "Hawkish قوي 🔴"
    elif final_hawk >= 55: final_tone = "Hawkish خفيف 🟡"
    elif final_dove >= 70: final_tone = "Dovish قوي 🟢"
    elif final_dove >= 55: final_tone = "Dovish خفيف 🟡"
    else:                  final_tone = "محايد ⚪"

    report = f"""
تحليل نبرة الفيدرالي
━━━━━━━━━━━━━━━━━━━━━
النبرة الإجمالية: {final_tone}
Hawkish: {final_hawk}% | Dovish: {final_dove}%

آخر التصريحات:"""

    for r in results:
        report += f"\n• {r['title'][:60]}..."
        report += f"\n  النبرة: {r['tone']} | H:{r['hawk']}% D:{r['dove']}%"

    return report, final_hawk, final_dove

if __name__ == "__main__":
    print("اختبار tone.py...")
    report, hawk, dove = get_tone_report()
    print(report)
    print(f"\nNبرة إجمالية: Hawkish {hawk}% | Dovish {dove}%")
