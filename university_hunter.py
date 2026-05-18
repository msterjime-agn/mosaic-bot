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

UNIVERSITIES = [
    {"name": "Kütahya Dumlupınar Üniversitesi", "url": "https://iro.dpu.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "kesin kayıt", "ek yerleştirme"]},
    {"name": "Çukurova Üniversitesi", "url": "https://iso.cu.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "aday öğrenci", "kesin kayıt"]},
    {"name": "Trakya Üniversitesi", "url": "https://disiliskiler.trakya.edu.tr/", "keywords": ["2026-2027", "yurtdışından öğrenci", "başvuru", "kesin kayıt"]},
    {"name": "Kafkas Üniversitesi", "url": "https://www.kafkas.edu.tr/", "keywords": ["2026-2027", "yabancı uyruklu", "uluslararası öğrenci", "başvuru", "kesin kayıt"]},
    {"name": "Ardahan Üniversitesi", "url": "https://www.ardahan.edu.tr/", "keywords": ["2026-2027", "yabancı uyruklu", "uluslararası öğrenci", "başvuru"]},
    {"name": "Afyon Kocatepe Üniversitesi", "url": "https://yos.aku.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yerleştirme", "kesin kayıt"]},
    {"name": "Zonguldak Bülent Ecevit Üniversitesi", "url": "https://iso.beun.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "ek kontenjan", "kesin kayıt"]},
    {"name": "Uşak Üniversitesi", "url": "https://admission.usak.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "kesin kayıt"]},
    {"name": "Karadeniz Teknik Üniversitesi", "url": "https://www.ktu.edu.tr/oidb", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Recep Tayyip Erdoğan Üniversitesi", "url": "https://iso.erdogan.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "kesin kayıt"]},
    {"name": "Süleyman Demirel Üniversitesi", "url": "https://w3.sdu.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Balıkesir Üniversitesi", "url": "https://www.balikesir.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Selçuk Üniversitesi", "url": "https://www.selcuk.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Atatürk Üniversitesi", "url": "https://www.atauni.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu", "kesin kayıt"]},
    {"name": "Ondokuz Mayıs Üniversitesi", "url": "https://www.omu.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Muğla Sıtkı Koçman Üniversitesi", "url": "https://www.mu.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Sakarya Uygulamalı Bilimler Üniversitesi", "url": "https://studyin.subu.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "kesin kayıt"]},
    {"name": "Anadolu Üniversitesi", "url": "https://www.anadolu.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Kastamonu Üniversitesi", "url": "https://www.kastamonu.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Bartın Üniversitesi", "url": "https://w3.bartin.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Aksaray Üniversitesi", "url": "https://www.aksaray.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Yozgat Bozok Üniversitesi", "url": "https://www.bozok.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Bayburt Üniversitesi", "url": "https://www.bayburt.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Gümüşhane Üniversitesi", "url": "https://www.gumushane.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Siirt Üniversitesi", "url": "https://www.siirt.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Bitlis Eren Üniversitesi", "url": "https://www.beu.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Iğdır Üniversitesi", "url": "https://www.igdir.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Kilis 7 Aralık Üniversitesi", "url": "https://www.kilis.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Erzincan Binali Yıldırım Üniversitesi", "url": "https://www.ebyu.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Tokat Gaziosmanpaşa Üniversitesi", "url": "https://www.gop.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Karamanoğlu Mehmetbey Üniversitesi", "url": "https://www.kmu.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Nevşehir Hacı Bektaş Veli Üniversitesi", "url": "https://www.nevsehir.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Niğde Ömer Halisdemir Üniversitesi", "url": "https://www.ohu.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Kırıkkale Üniversitesi", "url": "https://www.kku.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Bolu Abant İzzet Baysal Üniversitesi", "url": "https://www.ibu.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Ordu Üniversitesi", "url": "https://www.odu.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
    {"name": "Amasya Üniversitesi", "url": "https://www.amasya.edu.tr/", "keywords": ["2026-2027", "uluslararası öğrenci", "başvuru", "yabancı uyruklu"]},
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


def get_hash(text):
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

        if any(x in href.lower() for x in [
            ".pdf",
            "duyuru",
            "haber",
            "basvuru",
            "başvuru",
            "aday",
            "ogrenci",
            "ögrenci",
            "uluslararasi",
            "uluslararası"
        ]):
            links.append(f"{title} {href}")

    full_text = text + " " + " ".join(links)
    return full_text


async def send_message(bot, text):
    await bot.send_message(
        chat_id=CHAT_ID,
        text=text[:3900],
        disable_web_page_preview=False
    )


def extract_snippets(text, keywords):
    sentences = re.split(r"[.!?\n]", text)
    snippets = []

    for s in sentences:
        ns = normalize(s)
        if any(normalize(k) in ns for k in keywords):
            clean = " ".join(s.split())
            if 20 < len(clean) < 300:
                snippets.append(clean)

    return snippets[:5]


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

            found_keywords = [
                keyword for keyword in keywords
                if normalize(keyword) in normalized
            ]

            if old_hash is None:
                state[url] = current_hash
                await send_message(
                    bot,
                    f"✅ İlk kayıt yapıldı\n\n"
                    f"🏫 {name}\n"
                    f"🔗 {url}"
                )

            elif old_hash != current_hash:
                state[url] = current_hash

                if found_keywords:
                    snippets = extract_snippets(text, keywords)

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
                f"⚠️ Hata\n\n"
                f"🏫 {name}\n"
                f"🔗 {url}\n\n"
                f"{e}"
            )

    save_state(state)


async def university_hunter_loop():
    while True:
        await check_universities()
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(university_hunter_loop())
