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

CHECK_INTERVAL = 21600  # 6 часов
STATE_FILE = "university_state.json"

UNIVERSITIES = [
    {
        "name": "Kütahya Dumlupınar Üniversitesi",
        "url": "https://iso.dpu.edu.tr/"
    },
    {
        "name": "Çukurova Üniversitesi",
        "url": "https://iso.cu.edu.tr/"
    },
    {
        "name": "Trakya Üniversitesi",
        "url": "https://disiliskiler.trakya.edu.tr/"
    },
    {
        "name": "Karadeniz Teknik Üniversitesi",
        "url": "https://www.ktu.edu.tr/oidb"
    },
    {
        "name": "Afyon Kocatepe Üniversitesi",
        "url": "https://yos.aku.edu.tr/"
    },
    {
        "name": "Uşak Üniversitesi",
        "url": "https://admission.usak.edu.tr/"
    }
]

KEYWORDS = [
    "uluslararası öğrenci",
    "yabancı öğrenci",
    "diploma",
    "lise",
    "başvuru",
    "kayıt",
    "2026-2027",
    "ön kayıt",
    "international student"
]

NEGATIVE_KEYWORDS = [
    "erasmus",
    "mevlana",
    "farabi",
    "personel",
    "yüksek lisans",
    "master",
    "doktora",
    "konferans",
    "haber"
]


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def text_hash(text):
    return hashlib.md5(text.encode()).hexdigest()


def contains_keywords(text):
    text_lower = text.lower()

    positive = any(k in text_lower for k in KEYWORDS)
    negative = any(k in text_lower for k in NEGATIVE_KEYWORDS)

    return positive and not negative


def extract_dates(text):
    pattern = r"\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b"
    return re.findall(pattern, text)


async def send_message(bot, text, url):
    keyboard = [
        [InlineKeyboardButton("🔗 Aç", url=url)]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await bot.send_message(
        chat_id=CHAT_ID,
        text=text,
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

            text = response.text

            soup = BeautifulSoup(text, "html.parser")

            clean_text = soup.get_text(" ", strip=True)

            if not contains_keywords(clean_text):
                print(f"NO RELEVANT UPDATE: {name}", flush=True)
                continue

            snippets = []

            for line in clean_text.split("."):
                line = line.strip()

                if len(line) < 20:
                    continue

                if contains_keywords(line):
                    snippets.append(line[:300])

            snippets = snippets[:5]

            message_hash = text_hash(clean_text[:5000])

            old_hash = state.get(url)

            if old_hash == message_hash:
                print(f"NO CHANGES: {name}", flush=True)
                continue

            state[url] = message_hash
            save_state(state)

            dates = extract_dates(clean_text)

            msg = (
                f"✅ İlk kayıt bulundu\n\n"
                f"🏫 {name}\n"
                f"📌 Konu: Uluslararası öğrenci / diploma ile başvuru\n"
                f"🔗 {url}\n\n"
            )

            if dates:
                msg += "📅 Tarihler:\n"
                for d in dates[:10]:
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
            print(f"ERROR {name}: {e}", flush=True)

    print(f"SLEEPING {CHECK_INTERVAL} sec", flush=True)


async def main():
    while True:
        await check_universities()
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
