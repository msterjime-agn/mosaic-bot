import os
import time
import re
import json
import random
import threading
import webbrowser
from pathlib import Path
from datetime import datetime, date
from html import unescape
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

# ====================== ЗАГРУЗКА .env ======================
def load_env():
    env_path = '.env'
    if os.path.exists(env_path):
        print(f"✅ .env загружен")
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env()

# ========================= CONFIG =========================
TOKEN = os.getenv('TOKEN', '8574441866:AAHnn3FdSMoqWQblo66P8zc9k_I_OVyHw2Q')
CHAT_ID = os.getenv('CHAT_ID', '-1003682526875')
BOT_NAME = os.getenv('BOT_NAME', 'MOSAIC-ULTRA')

CALENDARS = {'Ashgabat': 11, 'Ashgabat VIP': 12, 'Ashgabat Student Visa': 20}
MONTHS_AHEAD = int(os.getenv('MONTHS_AHEAD', '8'))
MAX_WORKERS = int(os.getenv('MAX_WORKERS', '9'))

NORMAL_SLEEP_MIN = float(os.getenv('NORMAL_SLEEP_MIN', '4'))
NORMAL_SLEEP_MAX = float(os.getenv('NORMAL_SLEEP_MAX', '8'))
TURBO_SLEEP_MIN = float(os.getenv('TURBO_SLEEP_MIN', '1.5'))
TURBO_SLEEP_MAX = float(os.getenv('TURBO_SLEEP_MAX', '3'))

REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))
HEARTBEAT_INTERVAL = int(os.getenv('HEARTBEAT_INTERVAL', '900'))
STATUS_INTERVAL = int(os.getenv('STATUS_INTERVAL', '3600'))
ALERT_COOLDOWN = int(os.getenv('ALERT_COOLDOWN', '600'))
ERROR_COOLDOWN = int(os.getenv('ERROR_COOLDOWN', '1800'))
FLOOD_ALERT_DELAY = float(os.getenv('FLOOD_ALERT_DELAY', '3'))

STUDENT_SMS_COUNT = int(os.getenv('STUDENT_SMS_COUNT', '2'))
STANDARD_SMS_COUNT = int(os.getenv('STANDARD_SMS_COUNT', '5'))
VIP_SMS_COUNT = int(os.getenv('VIP_SMS_COUNT', '12'))

CONFIRM_BEFORE_ALERT = os.getenv('CONFIRM_BEFORE_ALERT', '1') == '1'
MAX_SLOT_COUNT = int(os.getenv('MAX_SLOT_COUNT', '2000'))
SIGNAL_ON_RESERVED = os.getenv('SIGNAL_ON_RESERVED', '1') == '1'
SIGNAL_HOT_COOLDOWN = int(os.getenv('SIGNAL_HOT_COOLDOWN', '120'))
SIGNAL_COOLDOWN = int(os.getenv('SIGNAL_COOLDOWN', '900'))
AUTO_OPEN_BROWSER_ON_SLOT = os.getenv('AUTO_OPEN_BROWSER_ON_SLOT', '1') == '1'
SEND_HTML_ON_SLOT = os.getenv('SEND_HTML_ON_SLOT', '1') == '1'
ENABLE_COMMANDS = os.getenv('ENABLE_COMMANDS', '1') == '1'
ENABLE_TURBO_AFTER_SLOT = os.getenv('ENABLE_TURBO_AFTER_SLOT', '1') == '1'
TURBO_SECONDS_AFTER_SLOT = int(os.getenv('TURBO_SECONDS_AFTER_SLOT', '300'))

PROXY_URL = os.getenv('PROXY_URL', '').strip()
PROXIES = {'http': PROXY_URL, 'https': PROXY_URL} if PROXY_URL else None

BASE_DIR = Path('./mosaic_bot_data')
BASE_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = BASE_DIR / 'mosaic_ultra.log'
STATE_FILE = BASE_DIR / 'mosaic_ultra_state.json'
HISTORY_FILE = BASE_DIR / 'mosaic_slot_history.jsonl'
SNAP_DIR = BASE_DIR / 'mosaic_snaps'
SNAP_DIR.mkdir(parents=True, exist_ok=True)

last_heartbeat_time = 0
last_status_time = 0
last_update_id = None
paused = False
turbo_until = 0
last_alert_time_by_key = {}
last_error_time_by_key = {}
last_signal_time_by_key = {}
last_change_alert_time_by_key = {}

MONTH_NAMES_RU = {1:'Январь',2:'Февраль',3:'Март',4:'Апрель',5:'Май',6:'Июнь',7:'Июль',8:'Август',9:'Сентябрь',10:'Октябрь',11:'Ноябрь',12:'Декабрь'}
EN_MONTH_TO_NUM = {'january':1,'jan':1,'february':2,'feb':2,'march':3,'mar':3,'april':4,'apr':4,'may':5,'june':6,'jun':6,'july':7,'jul':7,'august':8,'aug':8,'september':9,'sep':9,'sept':9,'october':10,'oct':10,'november':11,'nov':11,'december':12,'dec':12}

def log(text):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}"
    print(line, flush=True)
    try:
        LOG_FILE.open('a', encoding='utf-8').write(line + '\n')
    except Exception:
        pass

def tg(method, data=None, files=None, timeout=30):
    try:
        r = requests.post(f'https://api.telegram.org/bot{TOKEN}/{method}', data=data or {}, files=files, timeout=timeout, proxies=PROXIES)
        log(f'TG {method}: {r.status_code} {r.text[:250]}')
        return r
    except Exception as e:
        log(f'TG ERROR {method}: {e}')
        return None

def send_message(text, silent=False):
    r = tg('sendMessage', {'chat_id': CHAT_ID, 'text': text, 'disable_notification': silent})
    return bool(r and r.ok)

def send_document(path, caption=''):
    try:
        with open(path, 'rb') as f:
            r = tg('sendDocument', {'chat_id': CHAT_ID, 'caption': caption}, {'document': f}, 60)
        return bool(r and r.ok)
    except Exception as e:
        log(f'SEND DOCUMENT ERROR: {e}')
        return False

def load_state():
    default = {'seen_slots': {}, 'last_stats': {}, 'last_circle_time': '', 'slot_map': {}, 'page_states': {}, 'last_change_time': ''}
    try:
        if not STATE_FILE.exists():
            return default
        state = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        for k, v in default.items():
            state.setdefault(k, v)
        return state
    except Exception:
        return default

def save_state(state):
    try:
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as e:
        log(f'STATE SAVE ERROR: {e}')

def append_history(item):
    try:
        HISTORY_FILE.open('a', encoding='utf-8').write(json.dumps(item, ensure_ascii=False) + '\n')
    except Exception as e:
        log(f'HISTORY ERROR: {e}')

def month_add(y, m, add):
    total = y * 12 + (m - 1) + add
    return total // 12, total % 12 + 1

def months_to_check():
    today = date.today()
    out = []
    for i in range(MONTHS_AHEAD):
        y, m = month_add(today.year, today.month, i)
        out.append((f'{y}-{m:02d}', f'{MONTH_NAMES_RU[m]} {y}', y, m))
    return out

def make_url(cid, mv):
    return f'https://appointment.mosaicvisa.com/calendar/{cid}?month={mv}'

def fetch(url):
    headers = {'User-Agent': random.choice(['Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/136 Safari/537.36', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0'])}
    for i in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, proxies=PROXIES)
            return r.text, r.status_code
        except Exception as e:
            log(f'FETCH RETRY {i+1}/3 {url}: {e}')
            time.sleep(random.uniform(1.5, 4))
    raise Exception("Fetch failed")

def clean_html(html):
    text = re.sub(r'<script\b[^>]*>.*?</script>', ' ', html, flags=re.I | re.S)
    text = re.sub(r'<style\b[^>]*>.*?</style>', ' ', text, flags=re.I | re.S)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = unescape(text)
    return re.sub(r'\s+', ' ', text).strip()

def parse_date_text(day_text, year_hint):
    parts = day_text.strip().replace(',', ' ').split()
    if len(parts) < 2:
        return None
    try:
        d = int(parts[0])
    except Exception:
        return None
    m = EN_MONTH_TO_NUM.get(parts[1].lower())
    if not m:
        return None
    y = year_hint
    if len(parts) >= 3:
        try:
            y = int(parts[2])
        except Exception:
            pass
    try:
        return date(y, m, d)
    except Exception:
        return None

BASE_SITE = 'https://appointment.mosaicvisa.com'

def _abs_url(href):
    href = (href or '').strip()
    if not href:
        return ''
    if href.startswith('http'):
        return href
    if href.startswith('/'):
        return BASE_SITE + href
    return BASE_SITE + '/' + href

def extract_day_links(html):
    links = {}
    try:
        for m in re.finditer(r'href\s*=\s*["\']([^"\']*?(\d{4}-\d{2}-\d{2})[^"\']*)["\']', html, flags=re.I):
            links[m.group(2)] = _abs_url(m.group(1))
        for m in re.finditer(r'data-(?:date|day)\s*=\s*["\'](\d{4}-\d{2}-\d{2})["\'][^>]{0,200}?href\s*=\s*["\']([^"\']+)["\']', html, flags=re.I | re.S):
            links.setdefault(m.group(1), _abs_url(m.group(2)))
    except Exception as e:
        log(f'LINK PARSE ERROR: {e}')
    return links

def parse_calendar_rows(html):
    out = {}
    for m in re.finditer(r'<tr\b([^>]*)>(.*?)</tr>', html, flags=re.I | re.S):
        tag, body = m.group(1), m.group(2)
        if 'calendar-dates' not in tag:
            continue
        dm = re.search(r'data-date\s*=\s*"([^"]*)"', tag)
        iso = (dm.group(1) if dm else '').strip()
        if not iso:
            continue
        rm = re.search(r'data-remaining\s*=\s*"(\d+)"', tag)
        rem = int(rm.group(1)) if rm else 0
        txt = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', body)).strip()
        vr = re.search(r'Reserved[^0-9]{0,20}(\d+)', txt, flags=re.I)
        resv = int(vr.group(1)) if vr else None
        out[iso] = {'r': rem, 'v': resv, 'c': ('cursor: pointer' in tag.lower())}
    return out

def parse_slots(html, year_hint, label_ctx=''):
    today = date.today()
    res = {}
    rows_seen = 0
    for m in re.finditer(r'<tr\b[^>]*>', html, flags=re.I | re.S):
        tag = m.group(0)
        if 'calendar-dates' not in tag:
            continue
        rows_seen += 1
        dm = re.search(r'data-date\s*=\s*"(\d{4}-\d{2}-\d{2})"', tag)
        rm = re.search(r'data-remaining\s*=\s*"(\d+)"', tag)
        if not dm or not rm:
            continue
        iso = dm.group(1)
        try:
            cnt = int(rm.group(1))
        except Exception:
            continue
        try:
            dt = date.fromisoformat(iso)
        except Exception:
            continue
        if dt < today or cnt <= 0:
            continue
        clickable = ('cursor: pointer' in tag.lower())
        fm = re.search(r'data-date-formatted\s*=\s*"([^"]*)"', tag)
        label = fm.group(1) if fm else iso
        if cnt > MAX_SLOT_COUNT:
            log(f'BIG OPENING [{label_ctx or "?"}] {iso}: {cnt} places')
        res[iso] = {'date': iso, 'text': label, 'count': cnt, 'clickable': clickable}
    if rows_seen:
        return sorted(res.values(), key=lambda x: x['date']), clean_html(html)
    return [], clean_html(html)

def detect_state(html, year_hint, label_ctx=''):
    slots, text = parse_slots(html, year_hint, label_ctx)
    if slots:
        return 'SLOTS_FOUND', slots, text
    if 'calendar-dates' in html:
        return 'ZERO_SLOTS', [], text
    return 'EMPTY_MONTH', [], text

def save_snapshot(prefix, html):
    path = SNAP_DIR / (re.sub(r'[^A-Za-z0-9_-]+', '_', prefix) + '_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.html')
    try:
        path.write_text(html, encoding='utf-8', errors='ignore')
        return str(path)
    except Exception as e:
        log(f'SNAP ERROR: {e}')
        return ''

def check_one(task):
    name, cid, mv, mt, y = task
    url = make_url(cid, mv)
    key = f'{name} / {mt}'
    try:
        html, status = fetch(url)
        if status != 200:
            return {'ok': False, 'state': 'HTTP_ERROR', 'key': key, 'url': url, 'error': f'HTTP {status}', 'slots': [], 'calendar_name': name, 'month_title': mt, 'month_value': mv}
        st, slots, text = detect_state(html, y, key)
        snap = save_snapshot(f'{name}_{mv}_{st}', html) if st in ('SLOTS_FOUND', 'UNKNOWN') else ''
        day_links = extract_day_links(html) if st == 'SLOTS_FOUND' else {}
        cal = parse_calendar_rows(html)
        return {'ok': st != 'UNKNOWN', 'state': st, 'key': key, 'url': url, 'slots': slots, 'snapshot': snap, 'day_links': day_links, 'cal': cal, 'calendar_name': name, 'month_title': mt, 'month_value': mv}
    except Exception as e:
        return {'ok': False, 'state': 'ERROR', 'key': key, 'url': url, 'error': str(e), 'slots': [], 'calendar_name': name, 'month_title': mt, 'month_value': mv}

def build_tasks():
    tasks = []
    for mv, mt, y, _ in months_to_check():
        for name, cid in CALENDARS.items():
            tasks.append((name, cid, mv, mt, y))
    random.shuffle(tasks)
    return tasks

def tier_of(calendar_name):
    n = calendar_name.lower()
    if 'student' in n:
        return '🟢', 'STUDENT', STUDENT_SMS_COUNT
    if 'vip' in n:
        return '🔴', 'VIP', VIP_SMS_COUNT
    return '🟡', 'STANDARD', STANDARD_SMS_COUNT

def fmt_date(iso):
    try:
        return datetime.fromisoformat(iso).strftime('%d.%m.%Y')
    except Exception:
        return iso

def mark_changed(state):
    state['last_change_time'] = datetime.now().strftime('%d.%m.%Y %H:%M:%S')

def smart_diff(state, result, commit=True):
    slot_map = state.setdefault('slot_map', {})
    key = result['key']
    old = slot_map.get(key, {})
    cur = {x['date']: x['count'] for x in result['slots']}
    new_dates = {d: c for d, c in cur.items() if d not in old}
    changed = {d: (old[d], c) for d, c in cur.items() if d in old and old[d] != c}
    if commit:
        slot_map[key] = cur
        if new_dates or changed:
            mark_changed(state)
        save_state(state)
    return new_dates, changed, {}

def alert_slots(result, state):
    global turbo_until
    new_dates, changed, _ = smart_diff(state, result, commit=True)
    if not new_dates and not changed:
        return
    emoji, tier, _ = tier_of(result['calendar_name'])

    # Новый слот или увеличение количества мест = сообщение
    increased = {
        d: (old, new)
        for d, (old, new) in changed.items()
        if new > old
    }

    # Только уменьшение мест — молча
    if not new_dates and not increased:
        log(f'[{result["key"]}] уменьшение мест — без Telegram')
        return

    lines = []

    for d in sorted(new_dates):
        lines.append(f"🆕 {fmt_date(d)} — {new_dates[d]} мест")

    for d in sorted(increased):
        old, new = increased[d]
        lines.append(f"📈 {fmt_date(d)} — мест стало больше: {old} → {new}")

    msg = (
    f"🚨 {emoji} {tier} СЛОТЫ НАЙДЕНЫ [{BOT_NAME}]\n"
    f"{result['calendar_name']}\n"
    f"{result['month_title']}\n\n"
    + "\n".join(lines)
    + f"\n{result['url']}"
)

    # Одно сообщение без флудера
    send_message(msg)
    if AUTO_OPEN_BROWSER_ON_SLOT:
        try:
            webbrowser.open(result['url'])
        except:
            pass
    if ENABLE_TURBO_AFTER_SLOT:
        turbo_until = time.time() + TURBO_SECONDS_AFTER_SLOT

def early_signal(result, state):
    pass  # можно расширить позже

def command_loop(state):
    global last_update_id
    while True:
        try:
            data = {'timeout': 20}
            if last_update_id is not None:
                data['offset'] = last_update_id + 1
            r = requests.post(f'https://api.telegram.org/bot{TOKEN}/getUpdates', data=data, timeout=30, proxies=PROXIES)
            if not r.ok:
                time.sleep(5)
                continue
            for upd in r.json().get('result', []):
                last_update_id = upd.get('update_id', last_update_id)
                msg = upd.get('message') or {}
                text = msg.get('text', '')
                if text.startswith('/'):
                    # handle_command здесь можно добавить
                    pass
        except Exception:
            time.sleep(5)

def main():
    global turbo_until
    log(f'🚀 BOT START {BOT_NAME}')
    send_message(f'✅ ULTRA v6 запущен — {BOT_NAME}', False)
    state = load_state()
    if ENABLE_COMMANDS:
        threading.Thread(target=command_loop, args=(state,), daemon=True).start()
    while True:
        if paused:
            time.sleep(5)
            continue
        tasks = build_tasks()
        stats = {}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            for fut in as_completed({ex.submit(check_one, t): t for t in tasks}):
                result = fut.result()
                st = result['state']
                stats[st] = stats.get(st, 0) + 1
                early_signal(result, state)
                if st == 'SLOTS_FOUND':
                    alert_slots(result, state)
        sl = random.uniform(TURBO_SLEEP_MIN, TURBO_SLEEP_MAX) if time.time() < turbo_until else random.uniform(NORMAL_SLEEP_MIN, NORMAL_SLEEP_MAX)
        time.sleep(sl)

if __name__ == '__main__':
    main()
