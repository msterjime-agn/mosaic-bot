import os
import time
import requests
import re
import random
from pathlib import Path
from datetime import datetime

TOKEN = "8574441866:AAHnn3FdSMoqWQblo66P8zc9k_I_OVyHw2Q"
CHAT_ID = "-1003682526875"
BOT_NAME = "MOSAIC-1"

URLS = {
    "Aprel 2026": "https://appointment.mosaicvisa.com/calendar/11?month=2026-04",
    "Maý 2026":   "https://appointment.mosaicvisa.com/calendar/11?month=2026-05",
    "Iýun 2026":  "https://appointment.mosaicvisa.com/calendar/11?month=2026-06",
}

CHECK_INTERVAL_MIN = 8
CHECK_INTERVAL_MAX = 12
REQUEST_TIMEOUT = 60

SLOT_REPEAT_COUNT = 2
SLOT_REPEAT_DELAY = 1
STATUS_INTERVAL = 1300

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

last_status_time = 0
last_slot_signature = ""


def log(text: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now}] {text}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def send_message(text: str):
    for i in range(3):
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
            log(f"SEND RETRY {i+1}/3 ERROR: {e}")
            time.sleep(5)
    return False


def send_voice_siren():
    if not SIREN_FILE.exists():
        log(f"VOICE ERROR: file not found -> {SIREN_FILE}")
        return False

    for i in range(3):
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
            log(f"VOICE RETRY {i+1}/3 ERROR: {e}")
            time.sleep(5)
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


def fetch(url: str):
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    last_error = None

    for i in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            return r.text, r.status_code
        except Exception as e:
            last_error = e
            log(f"RETRY {i + 1}/3: {e}")
            time.sleep(random.uniform(4, 8))

    raise last_error


def parse_slot_entries(html: str):
    pattern = re.compile(
        r'(\d{1,2}\s+[A-Za-z]+\s+\d{4}).*?Available[^0-9]*([0-9]+)',
        re.IGNORECASE | re.DOTALL
    )
    matches = pattern.findall(html)

    results = []
    for day_text, count_text in matches:
        try:
            count = int(count_text)
            if count > 0:
                results.append((day_text.strip(), count))
        except Exception:
            pass

    return results


def send_status(ok_count: int, bad_count: int):
    global last_status_time
    now = time.time()

    if now - last_status_time < STATUS_INTERVAL:
        return

    msg = (
        f"ℹ️ STATUS\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')}\n"
        f"✅ Месяцев без ошибок: {ok_count}\n"
        f"⚠️ Месяцев с ошибками: {bad_count}\n"
        f"🤖 Бот работает [{BOT_NAME}]"
    )

    if send_message(msg):
        last_status_time = now


def alert_slots(month_name: str, slot_entries, url: str):
    global last_slot_signature

    total = sum(count for _, count in slot_entries)
    days = len(slot_entries)
    nearest_day = slot_entries[0][0]
    nearest_count = slot_entries[0][1]

    signature = f"{month_name}|{nearest_day}|{nearest_count}|{total}|{days}"

    if signature == last_slot_signature:
        log(f"[{month_name}] SAME SLOT SIGNATURE, alert skipped")
        return

    msg = (
        f"🔥🔥🔥 СЛОТЫ НАЙДЕНЫ!!! [{BOT_NAME}]\n"
        f"📅 {month_name}\n"
        f"📍 Ближайшая дата: {nearest_day}\n"
        f"👤 На ближайшую дату: {nearest_count}\n"
        f"🗓 Дней с местами: {days}\n"
        f"📦 Всего мест за месяц: {total}\n"
        f"👉 {url}"
    )

    send_voice_siren()

    sent_any = False
    for _ in range(SLOT_REPEAT_COUNT):
        ok = send_message(msg)
        sent_any = sent_any or ok
        time.sleep(SLOT_REPEAT_DELAY)

    if sent_any:
        last_slot_signature = signature


def check_month(name: str, url: str):
    try:
        html, status = fetch(url)

        if status != 200:
            log(f"[{name}] HTTP {status}")
            send_message(f"⚠️ {name} HTTP {status} [{BOT_NAME}]")
            return False

        slot_entries = parse_slot_entries(html)
        log(f"[{name}] PARSED SLOT ENTRIES: {slot_entries}")

        if slot_entries:
            total = sum(c for _, c in slot_entries)
            days = len(slot_entries)
            log(f"[{name}] SLOT FOUND: {days} days / {total} places")
            save_snapshot(name, html)
            alert_slots(name, slot_entries, url)
            return True

        low = html.lower()
        if "reserved" in low or "available" in low or "calendar" in low:
            log(f"[{name}] calendar page loaded, but no available slots parsed")
        else:
            log(f"[{name}] boş")

        return True

    except Exception as e:
        log(f"[{name}] ERROR: {e}")
        send_message(f"⚠️ {name} ERROR [{BOT_NAME}]\n{e}")
        return False


def main():
    log(f"🚀 BOT START {BOT_NAME}")
    send_message(f"✅ PRO режим: бот запущен ({BOT_NAME})")

    while True:
        ok_count = 0
        bad_count = 0

        for name, url in URLS.items():
            ok = check_month(name, url)
            if ok:
                ok_count += 1
            else:
                bad_count += 1
            time.sleep(1)

        send_status(ok_count, bad_count)

        sleep_time = random.uniform(CHECK_INTERVAL_MIN, CHECK_INTERVAL_MAX)
        log(f"SLEEP: {round(sleep_time, 1)} sec")
        time.sleep(sleep_time)


if __name__ == "__main__":
    main()
