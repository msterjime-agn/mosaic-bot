import os
import time
import requests
import re
import random
from pathlib import Path
from datetime import datetime

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BOT_NAME = os.getenv("BOT_NAME", "MOSAIC-1")

URLS = {
    "Aprel 2026": "https://appointment.mosaicvisa.com/calendar/11?month=2026-04",
    "Maý 2026":   "https://appointment.mosaicvisa.com/calendar/11?month=2026-05",
    "Iýun 2026":  "https://appointment.mosaicvisa.com/calendar/11?month=2026-06",
}

CHECK_INTERVAL_MIN = 15
CHECK_INTERVAL_MAX = 25
REQUEST_TIMEOUT = 60

SLOT_REPEAT_COUNT = 7
SLOT_REPEAT_DELAY = 1

BASE_DIR = Path("/tmp/mosaic_bot")
BASE_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = BASE_DIR / "bot.log"
SNAP_DIR = BASE_DIR / "mosaic_snaps"
SNAP_DIR.mkdir(parents=True, exist_ok=True)

SIREN_FILE = Path("/app/siren.ogg")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
]

def log(text: str):
    now = datetime.now().strftime("%H:%M:%S")
    line = f"[{now}] {text}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def send_message(text: str):
    if not TOKEN or not CHAT_ID:
        log("SEND ERROR: TOKEN or CHAT_ID missing")
        return False

    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={
                "chat_id": CHAT_ID,
                "text": text,
                "disable_notification": False
            },
            timeout=20
        )
        log(f"SEND STATUS: {r.status_code}")
        log(f"SEND BODY: {r.text}")
        return r.ok
    except Exception as e:
        log(f"SEND ERROR: {e}")
        return False

def send_voice_siren():
    if not TOKEN or not CHAT_ID:
        log("VOICE ERROR: TOKEN or CHAT_ID missing")
        return False

    if not SIREN_FILE.exists():
        log(f"VOICE ERROR: file not found -> {SIREN_FILE}")
        return False

    try:
        with open(SIREN_FILE, "rb") as f:
            r = requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendVoice",
                data={"chat_id": CHAT_ID},
                files={"voice": f},
                timeout=30
            )
        log(f"VOICE STATUS: {r.status_code}")
        log(f"VOICE BODY: {r.text}")
        return r.ok
    except Exception as e:
        log(f"VOICE ERROR: {e}")
        return False

def save_snapshot(name: str, html: str):
    safe = name.replace(" ", "_")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SNAP_DIR / f"{safe}_{stamp}.html"
    try:
        path.write_text(html, encoding="utf-8", errors="ignore")
        log(f"SNAP SAVED: {path}")
    except Exception as e:
        log(f"SNAP ERROR: {e}")

def scream_slot(month: str, total: int, url: str):
    msg = (
        f"🔥🔥🔥 СЛОТ НАЙДЕН!!! [{BOT_NAME}]\n"
        f"📅 {month}\n"
        f"👤 Всего мест: {total}\n"
        f"👉 {url}"
    )

    send_voice_siren()

    for i in range(SLOT_REPEAT_COUNT):
        send_message(msg)
        time.sleep(SLOT_REPEAT_DELAY)

def fetch(url: str):
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Cache-Control": "no-cache"
    }

    last_error = None

    for i in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            return r.text, r.status_code
        except Exception as e:
            last_error = e
            log(f"RETRY {i + 1}: {e}")
            time.sleep(5)

    raise last_error

def parse_slots(html: str):
    matches = re.findall(r'Available\s+\S*\s*(\d+)', html, re.IGNORECASE)
    return [int(x) for x in matches if int(x) > 0]

def check_month(name: str, url: str):
    try:
        html, status = fetch(url)

        if status != 200:
            log(f"[{name}] HTTP {status}")
            return

        slots = parse_slots(html)

        if slots:
            total = sum(slots)
            log(f"[{name}] SLOT FOUND: {total}")
            save_snapshot(name, html)
            scream_slot(name, total, url)
        else:
            log(f"[{name}] boş")

    except Exception as e:
        log(f"[{name}] ERROR: {e}")
        send_message(f"⚠️ {name} ERROR [{BOT_NAME}]\n{e}")

def main():
    log(f"🚀 BOT START {BOT_NAME}")
    send_message(f"✅ PRO режим: бот запущен ({BOT_NAME})")

    while True:
        for name, url in URLS.items():
            check_month(name, url)
            time.sleep(2)

        sleep_time = random.uniform(CHECK_INTERVAL_MIN, CHECK_INTERVAL_MAX)
        log(f"SLEEP: {round(sleep_time, 1)} sec")
        time.sleep(sleep_time)

if __name__ == "__main__":
    main()
