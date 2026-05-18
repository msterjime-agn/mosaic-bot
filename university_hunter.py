import asyncio
import hashlib
import json
import os
import re

import requests
from bs4 import BeautifulSoup
from telegram import Bot

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

CHECK_INTERVAL = 21600  # 6 часов

UNIVERSITIES = [
    {
        "name": "Kütahya Dumlupınar Üniversitesi",
        "url": "https://iro.dpu.edu.tr/",
        "keywords": [
            "2026-2027",
            "uluslararası öğrenci",
            "başvuru",
            "kesin kayıt",
            "ek yerleştirme"
        ]
    },
    {
        "name": "Çukurova Üniversitesi",
        "url": "https://iso.cu.edu.tr/",
        "keywords": [
            "2026-2027",
            "uluslararası öğrenci",
            "başvuru",
            "aday öğrenci"
        ]
    },
    {
        "name": "Trakya Üniversitesi",
        "url": "https://disiliskiler.trakya.edu.tr/",
        "keywords": [
            "2026-2027",
            "yurtdışından öğrenci",
            "başvuru",
            "kesin kayıt"
        ]
    }
]

STATE_FILE = "university_state.json"


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
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
        "ç": "c"
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return " ".join(text.split())


def get_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()


def fetch_text(url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(url, headers=headers, timeout=30)

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    return soup.get_text(" ", strip=True)


async def send_message(bot, text):
    await bot.send_message(
        chat_id=CHAT_ID,
        text=text,
        disable_web_page_preview=False
    )


async def check_universities():
    bot = Bot(token=BOT_TOKEN)

    state = load_state()

    for uni in UNIVERSITIES:
        name = uni["name"]
        url = uni["url"]
        keywords = uni["keywords"]

        try:
            text = fetch_text(url)

            normalized = normalize(text)

            current_hash = get_hash(normalized)

            old_hash = state.get(url)

            found_keywords = []

            for keyword in keywords:
                if normalize(keyword) in normalized:
                    found_keywords.append(keyword)

            if old_hash is None:
                state[url] = current_hash

                await send_message(
                    bot,
                    f"✅ İlk kayıt yapıldı\n\n🏫 {name}\n🔗 {url}"
                )

            elif old_hash != current_hash:
                state[url] = current_hash

                if found_keywords:
                    snippets = []

                    sentences = re.split(r"[.!?\n]", text)

                    for s in sentences:
                        ns = normalize(s)

                        if any(normalize(k) in ns for k in keywords):
                            clean = " ".join(s.split())

                            if 20 < len(clean) < 250:
                                snippets.append(clean)

                    snippets = snippets[:5]

                    msg = (
                        f"🔔 Yeni üniversite duyurusu!\n\n"
                        f"🏫 {name}\n"
                        f"🔎 Kelimeler: {', '.join(found_keywords)}\n"
                        f"🔗 {url}\n\n"
                    )

                    if snippets:
                        msg += "📌 Bulunan metin:\n\n"

                        for s in snippets:
                            msg += f"• {s}\n"

                    await send_message(bot, msg)

            await asyncio.sleep(2)

        except Exception as e:
            await send_message(
                bot,
                f"⚠️ Hata\n\n{name}\n{url}\n\n{e}"
            )

    save_state(state)


async def university_hunter_loop():
    while True:
        await check_universities()

        await asyncio.sleep(CHECK_INTERVAL)
if __name__ == "__main__":
    asyncio.run(university_hunter_loop())
