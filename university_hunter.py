import asyncio
import hashlib
import json
import os
import re
from datetime import datetime, date
from urllib.parse import urljoin

import requests
import urllib3
from bs4 import BeautifulSoup
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Season mode: May-August is hot admission season.
CURRENT_MONTH = datetime.now().month
DEFAULT_INTERVAL = 600 if 5 <= CURRENT_MONTH <= 8 else 3600
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", str(DEFAULT_INTERVAL)))
REPEAT_OPEN_ALERT_INTERVAL = int(os.getenv("REPEAT_OPEN_ALERT_INTERVAL", "1800"))
STATE_FILE = os.getenv("STATE_FILE", "university_state_v2.json")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "25"))
MAX_LINKS_PER_UNI = int(os.getenv("MAX_LINKS_PER_UNI", "18"))

UNIVERSITIES = [
    {"name": "Kütahya Dumlupınar Üniversitesi", "url": "https://iro.dpu.edu.tr/"},
    {"name": "Çukurova Üniversitesi", "url": "https://iso.cu.edu.tr/"},
    {"name": "Trakya Üniversitesi", "url": "https://disiliskiler.trakya.edu.tr/"},
    {"name": "Kafkas Üniversitesi", "url": "https://www.kafkas.edu.tr/"},
    {"name": "Ardahan Üniversitesi", "url": "https://www.ardahan.edu.tr/"},
    {"name": "Afyon Kocatepe Üniversitesi", "url": "https://yos.aku.edu.tr/"},
    {"name": "Zonguldak Bülent Ecevit Üniversitesi", "url": "https://iso.beun.edu.tr/"},
    {"name": "Uşak Üniversitesi", "url": "https://admission.usak.edu.tr/"},
    {"name": "Karadeniz Teknik Üniversitesi", "url": "https://www.ktu.edu.tr/oidb"},
    {"name": "Recep Tayyip Erdoğan Üniversitesi", "url": "https://iso.erdogan.edu.tr/"},
    {"name": "Süleyman Demirel Üniversitesi", "url": "https://w3.sdu.edu.tr/"},
    {"name": "Balıkesir Üniversitesi", "url": "https://www.balikesir.edu.tr/"},
    {"name": "Selçuk Üniversitesi", "url": "https://www.selcuk.edu.tr/"},
    {"name": "Atatürk Üniversitesi", "url": "https://www.atauni.edu.tr/"},
    {"name": "Ondokuz Mayıs Üniversitesi", "url": "https://www.omu.edu.tr/"},
    {"name": "Muğla Sıtkı Koçman Üniversitesi", "url": "https://www.mu.edu.tr/"},
    {"name": "Sakarya Uygulamalı Bilimler Üniversitesi", "url": "https://studyin.subu.edu.tr/"},
    {"name": "Anadolu Üniversitesi", "url": "https://www.anadolu.edu.tr/"},
    {"name": "Kastamonu Üniversitesi", "url": "https://www.kastamonu.edu.tr/"},
    {"name": "Bartın Üniversitesi", "url": "https://w3.bartin.edu.tr/"},
    {"name": "Aksaray Üniversitesi", "url": "https://www.aksaray.edu.tr/"},
    {"name": "Yozgat Bozok Üniversitesi", "url": "https://www.bozok.edu.tr/"},
    {"name": "Bayburt Üniversitesi", "url": "https://www.bayburt.edu.tr/"},
    {"name": "Gümüşhane Üniversitesi", "url": "https://www.gumushane.edu.tr/"},
    {"name": "Siirt Üniversitesi", "url": "https://www.siirt.edu.tr/"},
    {"name": "Bitlis Eren Üniversitesi", "url": "https://www.beu.edu.tr/"},
    {"name": "Iğdır Üniversitesi", "url": "https://www.igdir.edu.tr/"},
    {"name": "Kilis 7 Aralık Üniversitesi", "url": "https://www.kilis.edu.tr/"},
    {"name": "Erzincan Binali Yıldırım Üniversitesi", "url": "https://www.ebyu.edu.tr/"},
    {"name": "Tokat Gaziosmanpaşa Üniversitesi", "url": "https://www.gop.edu.tr/"},
    {"name": "Karamanoğlu Mehmetbey Üniversitesi", "url": "https://www.kmu.edu.tr/"},
    {"name": "Nevşehir Hacı Bektaş Veli Üniversitesi", "url": "https://www.nevsehir.edu.tr/"},
    {"name": "Niğde Ömer Halisdemir Üniversitesi", "url": "https://www.ohu.edu.tr/"},
    {"name": "Kırıkkale Üniversitesi", "url": "https://www.kku.edu.tr/"},
    {"name": "Bolu Abant İzzet Baysal Üniversitesi", "url": "https://www.ibu.edu.tr/"},
    {"name": "Ordu Üniversitesi", "url": "https://www.odu.edu.tr/"},
    {"name": "Amasya Üniversitesi", "url": "https://www.amasya.edu.tr/"},
]

ADMISSION_TERMS = [
    "uluslararası öğrenci", "uluslararasi ogrenci", "yabancı uyruklu", "yabanci uyruklu",
    "yurtdışından öğrenci", "yurtdisindan ogrenci", "international student",
    "foreign student", "aday öğrenci", "aday ogrenci",
]

APPLICATION_TERMS = [
    "başvuru", "basvuru", "online başvuru", "online basvuru", "application",
    "apply", "admission", "kayıt", "kayit", "tercih", "yerleştirme", "yerlestirme",
]

CALENDAR_TERMS = [
    "takvim", "başvuru takvimi", "basvuru takvimi", "başvuru tarihleri", "basvuru tarihleri",
    "son başvuru", "son basvuru", "başvuru başlangıç", "basvuru baslangic",
    "başvuru bitiş", "basvuru bitis", "application dates", "deadline", "application deadline",
    "başlangıç tarihi", "baslangic tarihi", "bitiş tarihi", "bitis tarihi",
]

DIPLOMA_TERMS = [
    "lise diploması", "lise diplomasi", "diploma notu", "diploma puanı", "diploma puani",
    "ortaöğretim", "ortaogretim", "secondary school diploma", "high school diploma",
    "mezuniyet belgesi", "transkript", "graduation certificate", "diploma grade",
    "ortaöğretim başarı puanı", "ortaogretim basari puani",
]

YOS_TERMS = [
    "tr-yös", "tr-yos", "yös", "yos", "yabancı öğrenci sınavı", "yabanci ogrenci sinavi",
    "sat", "act", "gce", "abitur", "sınav", "sinav",
]

YOS_REQUIRED_TERMS = [
    "zorunludur", "zorunlu", "required", "şarttır", "sarttir", "kabul edilmeyecektir",
]

NEGATIVE_TERMS = [
    "erasmus", "mevlana", "farabi", "personel", "personel alımı", "personel alimi",
    "ihale", "akademik kadro", "iş ilanı", "is ilani", "yüksek lisans", "yuksek lisans",
    "master", "doktora", "phd", "konferans", "sempozyum", "yemek listesi", "spor",
    "mezuniyet töreni", "mezuniyet toreni", "haber", "duyuru arşivi", "duyuru arsivi",
]

MONTHS_TR = {
    "ocak": 1, "subat": 2, "şubat": 2, "mart": 3, "nisan": 4, "mayis": 5, "mayıs": 5,
    "haziran": 6, "temmuz": 7, "agustos": 8, "ağustos": 8, "eylul": 9, "eylül": 9,
    "ekim": 10, "kasim": 11, "kasım": 11, "aralik": 12, "aralık": 12,
}

DATE_PATTERNS = [
    r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b",
    r"\b\d{1,2}\s*(ocak|şubat|subat|mart|nisan|mayıs|mayis|haziran|temmuz|ağustos|agustos|eylül|eylul|ekim|kasım|kasim|aralık|aralik)\s*\d{4}\b",
    r"\b\d{1,2}\s*[-–]\s*\d{1,2}\s*(ocak|şubat|subat|mart|nisan|mayıs|mayis|haziran|temmuz|ağustos|agustos|eylül|eylul|ekim|kasım|kasim|aralık|aralik)\s*\d{4}\b",
    r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s*[-–]\s*\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b",
]

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8,ru;q=0.7",
}


def normalize(text: str) -> str:
    text = (text or "").lower()
    table = str.maketrans("ıüğşöçİÜĞŞÖÇ", "iugsociugsoc")
    text = text.translate(table)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def has_any(text: str, terms) -> bool:
    norm = normalize(text)
    return any(normalize(term) in norm for term in terms)


def text_hash(text: str) -> str:
    return hashlib.md5(normalize(text[:16000]).encode("utf-8")).hexdigest()


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_text(url: str):
    response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(" ", strip=True), soup


def is_relevant_link(title: str, href: str) -> bool:
    combined = f"{title} {href}"
    if has_any(combined, NEGATIVE_TERMS):
        return False
    if href.lower().endswith(".pdf") and (
        has_any(combined, ADMISSION_TERMS) or has_any(combined, APPLICATION_TERMS) or has_any(combined, DIPLOMA_TERMS) or "2026" in combined or "2027" in combined
    ):
        return True
    return has_any(combined, ADMISSION_TERMS + APPLICATION_TERMS + CALENDAR_TERMS + DIPLOMA_TERMS)


def collect_links(soup, base_url: str):
    links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        title = a.get_text(" ", strip=True)
        href = urljoin(base_url, a["href"])
        if href in seen:
            continue
        seen.add(href)
        if is_relevant_link(title, href):
            links.append({"title": title[:160] or href, "url": href})
        if len(links) >= MAX_LINKS_PER_UNI:
            break
    return links


def extract_dates(text: str):
    norm = normalize(text)
    dates = []
    for pattern in DATE_PATTERNS:
        for match in re.finditer(pattern, norm, flags=re.IGNORECASE):
            dates.append(match.group(0))
    return list(dict.fromkeys(dates))[:12]


def extract_context_snippets(text: str):
    raw_parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    snippets = []
    for part in raw_parts:
        clean = " ".join(part.split())
        if len(clean) < 35:
            continue
        if has_any(clean, NEGATIVE_TERMS):
            continue
        if has_any(clean, ADMISSION_TERMS + APPLICATION_TERMS + CALENDAR_TERMS + DIPLOMA_TERMS):
            snippets.append(clean[:350])
    return list(dict.fromkeys(snippets))[:6]


def detect_open_close(text: str):
    norm = normalize(text)
    open_found = has_any(norm, [
        "başvurular başlamıştır", "basvurular baslamistir", "başvurular başladı", "basvurular basladi",
        "başvurular açıldı", "basvurular acildi", "online başvuru", "online basvuru",
        "başvuru alınacaktır", "basvuru alinacaktir", "application is open", "applications are open",
    ])
    deadline_found = has_any(norm, [
        "son başvuru", "son basvuru", "başvuru bitiş", "basvuru bitis", "deadline",
        "application deadline", "başvurular sona", "basvurular sona", "bitiş tarihi", "bitis tarihi",
    ])
    calendar_found = has_any(norm, CALENDAR_TERMS)
    return open_found, deadline_found, calendar_found


def analyze_admission(full_text: str, links):
    norm = normalize(full_text)
    dates = extract_dates(full_text)
    snippets = extract_context_snippets(full_text)

    negative = has_any(norm, NEGATIVE_TERMS)
    admission = has_any(norm, ADMISSION_TERMS)
    application = has_any(norm, APPLICATION_TERMS)
    diploma = has_any(norm, DIPLOMA_TERMS)
    yos_seen = has_any(norm, YOS_TERMS)
    yos_required = yos_seen and has_any(norm, YOS_REQUIRED_TERMS)
    open_found, deadline_found, calendar_found = detect_open_close(norm)
    has_pdf = any(l["url"].lower().endswith(".pdf") for l in links)

    score = 0
    if admission: score += 3
    if application: score += 2
    if diploma: score += 4
    if open_found: score += 4
    if deadline_found: score += 4
    if calendar_found: score += 3
    if dates: score += 2
    if has_pdf: score += 1
    if negative: score -= 5

    important = score >= 6 and not negative
    category = "INFO"
    if diploma and (open_found or deadline_found or calendar_found):
        category = "🎓 ATTESTAT / DIPLOMA"
    elif open_found:
        category = "🔥 OPENED"
    elif deadline_found:
        category = "⏳ DEADLINE"
    elif calendar_found:
        category = "📅 TAKVIM"
    elif yos_required:
        category = "📝 SINAV / YÖS"

    if yos_required and not diploma:
        importance = "LOW"
    elif diploma and (open_found or deadline_found):
        importance = "CRITICAL"
    elif open_found or deadline_found or calendar_found:
        importance = "HIGH"
    else:
        importance = "MEDIUM"

    return {
        "important": important,
        "category": category,
        "importance": importance,
        "diploma": diploma,
        "yos_required": yos_required,
        "open_found": open_found,
        "deadline_found": deadline_found,
        "calendar_found": calendar_found,
        "dates": dates,
        "snippets": snippets,
        "links": links[:8],
        "score": score,
    }


def build_message(name: str, url: str, analysis):
    title = analysis["category"]
    importance = analysis["importance"]

    if importance == "CRITICAL":
        first = f"🚨 {title} | BAŞVURU TAKVİMİ BULUNDU"
    elif importance == "HIGH":
        first = f"🔥 {title} | ADMISSION UPDATE"
    else:
        first = f"ℹ️ {title} | POSSIBLE UPDATE"

    msg = (
        f"{first}\n\n"
        f"🏫 {name}\n"
        f"🎯 Hedef: Devlet üniversitesi / аттестат ile lisans başvuru\n"
        f"📊 Öncelik: {importance}\n"
    )

    if analysis["diploma"]:
        msg += "✅ Diploma/аттестат izleri bulundu\n"
    else:
        msg += "⚠️ Diploma/аттестат açık değil, kontrol lazım\n"

    if analysis["yos_required"]:
        msg += "📝 YÖS/SAT şartı olabilir\n"

    if analysis["open_found"]:
        msg += "🟢 Açılış/başvuru başladı ifadesi olabilir\n"
    if analysis["deadline_found"]:
        msg += "🔴 Son başvuru / kapanış tarihi olabilir\n"
    if analysis["calendar_found"]:
        msg += "📅 Takvim/tarih bilgisi bulundu\n"

    if analysis["dates"]:
        msg += "\n📅 Bulunan tarihler:\n"
        for d in analysis["dates"]:
            msg += f"• {d}\n"

    if analysis["snippets"]:
        msg += "\n📄 Parça metin:\n"
        for s in analysis["snippets"][:4]:
            msg += f"• {s}\n\n"

    if analysis["links"]:
        msg += "🔗 İlgili linkler:\n"
        for link in analysis["links"][:5]:
            label = link["title"][:70]
            msg += f"• {label}: {link['url']}\n"

    msg += f"\n🌐 Ana sayfa: {url}"
    return msg[:3900]


async def send_message(bot, text, url):
    keyboard = [[InlineKeyboardButton("🔗 Siteyi aç", url=url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await bot.send_message(
        chat_id=CHAT_ID,
        text=text,
        reply_markup=reply_markup,
        disable_web_page_preview=False,
    )


def should_send(state, url: str, message_hash: str, analysis):
    now_ts = int(datetime.now().timestamp())
    item = state.get(url, {}) if isinstance(state.get(url), dict) else {}
    old_hash = item.get("hash")
    last_alert = int(item.get("last_alert", 0))

    if old_hash != message_hash:
        return True, "NEW_OR_CHANGED"

    if analysis["importance"] in ("CRITICAL", "HIGH") and now_ts - last_alert >= REPEAT_OPEN_ALERT_INTERVAL:
        return True, "REPEAT_IMPORTANT"

    return False, "NO_CHANGE"


async def check_universities():
    print("=== START CHECK ===", flush=True)
    print(f"INTERVAL: {CHECK_INTERVAL} sec", flush=True)

    if not BOT_TOKEN or not CHAT_ID:
        print("ERROR: BOT_TOKEN or CHAT_ID is missing", flush=True)
        return

    bot = Bot(token=BOT_TOKEN)
    state = load_state()

    for uni in UNIVERSITIES:
        name = uni["name"]
        url = uni["url"]
        print(f"Checking: {name}", flush=True)

        try:
            clean_text, soup = fetch_text(url)
            links = collect_links(soup, url)
            links_text = " ".join([f"{l['title']} {l['url']}" for l in links])
            full_text = f"{clean_text} {links_text}"

            analysis = analyze_admission(full_text, links)

            if not analysis["important"]:
                print(f"NO RELEVANT ADMISSION UPDATE: {name} | score={analysis['score']}", flush=True)
                continue

            message_hash = text_hash(full_text + json.dumps(analysis["dates"], ensure_ascii=False))
            send, reason = should_send(state, url, message_hash, analysis)

            if not send:
                print(f"NO CHANGES: {name}", flush=True)
                continue

            msg = build_message(name, url, analysis)
            await send_message(bot, msg, url)

            state[url] = {
                "hash": message_hash,
                "last_alert": int(datetime.now().timestamp()),
                "last_reason": reason,
                "last_category": analysis["category"],
                "last_importance": analysis["importance"],
                "last_dates": analysis["dates"],
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
            save_state(state)

            print(f"FOUND/SENT: {name} | {analysis['category']} | {reason}", flush=True)
            await asyncio.sleep(2)

        except Exception as e:
            print(f"ERROR {name}: {str(e)[:220]}", flush=True)

    print(f"SLEEPING {CHECK_INTERVAL} sec", flush=True)


async def main():
    while True:
        await check_universities()
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
