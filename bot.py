import time
import requests
import re
import random
from pathlib import Path

TOKEN = "8574441866:AAHnn3FdSMoqWQblo66P8zc9k_I_OVyHw2Q"
CHAT_ID = "-1003682526875"

URLS = {
    "Aprel 2026": "https://appointment.mosaicvisa.com/calendar/11?month=2026-04",
    "Maý 2026":   "https://appointment.mosaicvisa.com/calendar/11?month=2026-05",
    "Iýun 2026":  "https://appointment.mosaicvisa.com/calendar/11?month=2026-06",
}

CHECK_INTERVAL_MIN = 15
CHECK_INTERVAL_MAX = 25
REQUEST_TIMEOUT = 60

SLOT_COOLDOWN = 300
ERROR_COOLDOWN = 600
STATUS_INTERVAL = 900
SLOT_REPEAT_COUNT = 7
SLOT_REPEAT_DELAY = 1

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
]

last_slot_signature = ""
last_slot_time = 0
last_error_signature = ""
last_error_time = 0
last_status_time = 0

BASE_DIR = Path.home() / "Desktop"
LOG_FILE = BASE_DIR / "mosaic_bot.log"
SNAP_DIR = BASE_DIR / "mosaic_snaps"
SNAP_DIR.mkdir(exist_ok=True)

def ts():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def log(msg: str):
    line = f"[{ts()}] {msg}"
    print(line)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def send_message(text: str) -> bool:
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={
                "chat_id": CHAT_ID,
                "text": text,
                "disable_notification": False,
            },
            timeout=30,
        )
        log(f"SEND STATUS: {r.status_code}")
        log(f"SEND BODY: {r.text}")
        return r.ok
    except Exception as e:
        log(f"SEND ERROR: {e}")
        return False

def save_snapshot(month_name: str, html: str) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    safe_name = month_name.replace(" ", "_")
    path = SNAP_DIR / f"{safe_name}_{stamp}.html"
    path.write_text(html, encoding="utf-8", errors="ignore")
    return path

def send_slot_alert(month_name: str, days: int, total: int, url: str, signature: str, snap_path: Path):
    global last_slot_signature, last_slot_time
    now = time.time()

    if signature == last_slot_signature and now - last_slot_time < SLOT_COOLDOWN:
        log("SLOT ALERT SKIPPED")
        return

    text = (
        "🔥🔥🔥 СЛОТ НАЙДЕН!!!\n\n"
        f"📅 {month_name}\n"
        f"🗓 Дней с местами: {days}\n"
        f"👤 Всего мест: {total}\n"
        f"📝 Снимок: {snap_path.name}\n\n"
        f"🌐 {url}\n\n"
        "🚀 Открой страницу и проверь сразу."
    )

    ok = False
    for _ in range(SLOT_REPEAT_COUNT):
        sent = send_message(text)
        ok = ok or sent
        time.sleep(SLOT_REPEAT_DELAY)

    if ok:
        last_slot_signature = signature
        last_slot_time = now

def send_error_alert(month_name: str, err_text: str):
    global last_error_signature, last_error_time
    now = time.time()
    signature = f"{month_name}:{err_text}"

    if signature == last_error_signature and now - last_error_time < ERROR_COOLDOWN:
        log("ERROR ALERT SKIPPED")
        return

    text = (
        "⚠️ ОШИБКА У БОТА\n\n"
        f"📅 {month_name}\n"
        f"🧨 {err_text}\n\n"
        "Бот продолжает работу."
    )

    if send_message(text):
        last_error_signature = signature
        last_error_time = now

def send_status(ok_count: int, bad_count: int):
    global last_status_time
    now = time.time()

    if now - last_status_time < STATUS_INTERVAL:
        return

    text = (
        "ℹ️ STATUS\n"
        f"⏰ {time.strftime('%H:%M:%S')}\n"
        f"✅ Месяцев без ошибок: {ok_count}\n"
        f"⚠️ Месяцев с ошибками: {bad_count}\n"
        "🤖 Бот работает"
    )

    if send_message(text):
        last_status_time = now

def fetch(url: str) -> str:
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru,en-US;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
    }

    last_error = None
    for attempt in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            return r.text
        except Exception as e:
            last_error = e
            log(f"RETRY {attempt + 1}/3: {e}")
            time.sleep(random.uniform(5, 12))

    raise last_error

def parse_slots(html: str):
    matches = re.findall(r'Available\s+\S*\s*(\d+)', html, flags=re.IGNORECASE)
    return [int(x) for x in matches if int(x) > 0]

def check():
    ok_count = 0
    bad_count = 0

    for month_name, url in URLS.items():
        try:
            html = fetch(url)
            available = parse_slots(html)

            if available:
                total = sum(available)
                days = len(available)
                log(f"🔥 {month_name}: {days} gün / {total} slot")
                snap = save_snapshot(month_name, html)
                signature = f"{month_name}:{days}:{total}"
                send_slot_alert(month_name, days, total, url, signature, snap)
            else:
                log(f"❌ {month_name}: boş")

            ok_count += 1

        except Exception as e:
            bad_count += 1
            err_text = str(e)
            log(f"[{month_name}] ERROR: {err_text}")
            send_error_alert(month_name, err_text)

        time.sleep(random.uniform(2, 5))

    send_status(ok_count, bad_count)

log("🚀 BOT START")
send_message("✅ PRO+ режим: бот запущен и мониторит Mosaic")

while True:
    check()
    sleep_for = random.uniform(CHECK_INTERVAL_MIN, CHECK_INTERVAL_MAX)
    log(f"SLEEP: {sleep_for:.1f} sec")
    time.sleep(sleep_for)
