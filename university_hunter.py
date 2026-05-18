import asyncio
import hashlib
import json
import os
import re
import urllib3

import requests
from bs4 import BeautifulSoup
from telegram import Bot

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

CHECK_INTERVAL = 21600  # 6 часов
STATE_FILE = "university_state.json"

MAIN_KEYWORDS = [
    "2026-2027",
    "uluslararası öğrenci",
    "yabancı uyruklu",
    "yurtdışından öğrenci",
    "başvuru",
    "başvuruları",
    "aday öğrenci",
    "kesin kayıt",
    "ek yerleştirme",
    "kontenjan"
]

DIPLOMA_KEYWORDS = [
    "diploma",
    "lise diploması",
    "diploma notu",
    "mezuniyet",
    "ortaöğretim",
    "secondary school",
    "high school diploma"
]

NEGATIVE_KEYWORDS = [
    "personel alımı",
    "ihale",
    "akademik kadro",
    "iş ilanı",
    "yemek listesi",
    "duyuru arşivi",
    "spor",
    "konferans",
    "sempozyum"
]

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


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def normalize(text):
    text = text.lower()
    replacements = {
        "ı": "i",
        "ğ": "g",
        "ü": "u",
        "ş": "s",
        "ö": "o",
        "ç": "c",
        "İ": "i",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return " ".join(text.split())


def hash_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fetch_text(url):
    headers = {
        "User-Agent": "Mozilla/5.0 UniversityHunterBot"
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30,
        verify=False
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(" ", strip=True)

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        title = a.get_text(" ", strip=True)

        if href.startswith("/"):
            href = url.rstrip("/") + href

        combined = f"{title} {href}"
        norm = normalize(combined)

        if any(k in norm for k in MAIN_KEYWORDS + DIPLOMA_KEYWORDS):
            links.append(combined)

    return text + " " + " ".join(links)


def is_relevant(text):
    norm = normalize(text)

    if any(k in norm for k in NEGATIVE_KEYWORDS):
        return False

    has_main = any(normalize(k) in norm for k in MAIN_KEYWORDS)
    has_diploma = any(normalize(k) in norm for k in DIPLOMA_KEYWORDS)

    return has_main and has_diploma


def extract_snippets(text):
    sentences = re.split(r"[.!?\n]", text)
    snippets = []

    for s in sentences:
        clean = " ".join(s.split())
        norm = normalize(clean)

        has_main = any(normalize(k) in norm for k in MAIN_KEYWORDS)
        has_diploma = any(normalize(k) in norm for k in DIPLOMA_KEYWORDS)

        if has_main or has_diploma:
            if 25 < len(clean) < 350:
                snippets.append(clean)

    return snippets[:6]


async def send_message(bot, text):
    await bot.send_message(
        chat_id=CHAT_ID,
        text=text[:3900],
        disable_web_page_preview=False
    )


async def check_universities():
    bot = Bot(token=BOT_TOKEN)
    state = load_state()

    for uni in UNIVERSITIES:
        name = uni["name"]
        url = uni["url"]

        try:
            text = fetch_text(url)
            normalized = normalize(text)
            current_hash = hash_text(normalized)

            old_data = state.get(url, {})
            old_hash = old_data.get("page_hash")
            sent_hashes = old_data.get("sent_hashes", [])

            if old_hash is None:
                state[url] = {
                    "page_hash": current_hash,
                    "sent_hashes": []
                }
                await asyncio.sleep(2)
                continue

            if old_hash != current_hash:
                state[url]["page_hash"] = current_hash

                if is_relevant(text):
                    snippets = extract_snippets(text)
                    message_basis = name + url + " ".join(snippets)
                    message_hash = hash_text(normalize(message_basis))

                    if message_hash not in sent_hashes:
                        msg = (
                            f"🎓 Yeni başvuru duyurusu olabilir\n\n"
                            f"🏫 {name}\n"
                            f"📌 Konu: Uluslararası öğrenci / diploma ile başvuru\n"
                            f"🔗 {url}\n\n"
                        )

                        if snippets:
                            msg += "Bulunan metin:\n"
                            for s in snippets:
                                msg += f"• {s}\n"

                        await send_message(bot, msg)

                        sent_hashes.append(message_hash)
                        state[url]["sent_hashes"] = sent_hashes[-20:]

            await asyncio.sleep(2)

        except Exception as e:
            error_key = f"error_{url}"
            last_error = state.get(error_key)

            error_text = str(e)[:250]

            if last_error != error_text:
                await send_message(
                    bot,
                    f"⚠️ Kontrol hatası\n\n"
                    f"🏫 {name}\n"
                    f"🔗 {url}\n\n"
                    f"{error_text}"
                )
                state[error_key] = error_text

    save_state(state)


async def university_hunter_loop():
    while True:
        await check_universities()
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(university_hunter_loop())
