import asyncio
import hashlib
import json
import os
import re
import urllib3

import requests
from bs4 import BeautifulSoup
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

CHECK_INTERVAL = 21600
STATE_FILE = "university_state.json"

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

KEYWORDS = [
    "2026-2027",
    "uluslararası öğrenci",
    "uluslararasi ogrenci",
    "yabancı uyruklu",
    "yabanci uyruklu",
    "yurtdışından öğrenci",
    "yurtdisindan ogrenci",
    "başvuru",
    "basvuru",
    "aday öğrenci",
    "aday ogrenci",
    "kesin kayıt",
    "kesin kayit",
    "ek yerleştirme",
    "ek yerlestirme",
    "kontenjan",
    "takvim",
    "kılavuz",
    "kilavuz",
    "diploma",
    "lise diploması",
    "lise diplomasi",
    "diploma notu",
    "mezuniyet",
    "ortaöğretim",
    "ortaogretim",
    "secondary school",
    "high school diploma",
    "international student",
]

NEGATIVE_KEYWORDS = [
    "erasmus",
    "mevlana",
    "farabi",
    "personel",
    "personel alımı",
    "personel alimi",
    "ihale",
    "akademik kadro",
    "iş ilanı",
    "is ilani",
    "yüksek lisans",
    "yuksek lisans",
    "master",
    "doktora",
    "konferans",
    "sempozyum",
    "yemek listesi",
    "spor",
    "haber",
]

DATE_PATTERNS = [
    r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b",
    r"\b\d{1,2}\s*(ocak|şubat|subat|mart|nisan|mayıs|mayis|haziran|temmuz|ağustos|agustos|eylül|eylul|ekim|kasım|kasim|aralık|aralik)\s*\d{4}\b",
]


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def normalize(text):
    text = text.lower()
    table = str.maketrans("ıüğşöçİ", "iugsoci")
    text = text.translate(table)
    return " ".join(text.split())


def text_hash(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def contains_keywords(text):
    norm = normalize(text)
    positive = any(normalize(k) in norm for k in KEYWORDS)
    negative = any(normalize(k) in norm for k in NEGATIVE_KEYWORDS)
    return positive and not negative


def extract_dates(text):
    dates = []
    norm = normalize(text)
    for pattern in DATE_PATTERNS:
        for match in re.finditer(pattern, norm, flags=re.IGNORECASE):
            dates.append(match.group(0))
    return list(dict.fromkeys(dates))[:10]


def extract_snippets(text):
    parts = re.split(r"[.!?\n]", text)
    snippets = []

    for part in parts:
        clean = " ".join(part.split())
        if len(clean) < 25:
            continue

        if contains_keywords(clean):
            snippets.append(clean[:300])

    return snippets[:5]


async def send_message(bot, text, url):
    keyboard = [[InlineKeyboardButton("🔗 Siteyi aç", url=url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await bot.send_message(
        chat_id=CHAT_ID,
        text=text[:3900],
        reply_markup=reply_markup,
        disable_web_page_preview=False
    )


async def check_universities():
    print("=== START CHECK ===", flush=True)

    bot = Bot(token=BOT_TOKEN)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }

    state = load_state()

    for uni in UNIVERSITIES:
        name = uni["name"]
        url = uni["url"]

        print(f"Checking: {name}", flush=True)

        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=25,
                verify=False
            )

            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()

            clean_text = soup.get_text(" ", strip=True)

            links_text = ""
            for a in soup.find_all("a", href=True):
                title = a.get_text(" ", strip=True)
                href = a["href"]

                if href.startswith("/"):
                    href = url.rstrip("/") + href

                combined = f"{title} {href}"

                if contains_keywords(combined) or ".pdf" in href.lower():
                    links_text += " " + combined

            full_text = clean_text + " " + links_text

            if not contains_keywords(full_text):
                print(f"NO RELEVANT UPDATE: {name}", flush=True)
                continue

            message_hash = text_hash(normalize(full_text[:8000]))
            old_hash = state.get(url)

            if old_hash == message_hash:
                print(f"NO CHANGES: {name}", flush=True)
                continue

            state[url] = message_hash
            save_state(state)

            dates = extract_dates(full_text)
            snippets = extract_snippets(full_text)

            msg = (
                f"🎓 Yeni başvuru duyurusu olabilir\n\n"
                f"🏫 {name}\n"
                f"📌 Konu: Uluslararası öğrenci / diploma ile başvuru\n"
                f"🔗 {url}\n\n"
            )

            if dates:
                msg += "📅 Tarihler:\n"
                for d in dates:
                    msg += f"• {d}\n"
                msg += "\n"

            if snippets:
                msg += "📄 Metin:\n"
                for s in snippets:
                    msg += f"• {s}\n\n"

            print(f"FOUND: {name}", flush=True)

            await send_message(bot, msg, url)
            await asyncio.sleep(2)

        except Exception as e:
            print(f"ERROR {name}: {str(e)[:180]}", flush=True)

    print(f"SLEEPING {CHECK_INTERVAL} sec", flush=True)


async def main():
    while True:
        await check_universities()
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
