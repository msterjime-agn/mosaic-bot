import os, time, re, json, random, threading, webbrowser
from pathlib import Path
from datetime import datetime, date
from html import unescape
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import smtplib
from email.message import EmailMessage

# ================= CONFIG =================

TOKEN=os.getenv('TOKEN','')
CHAT_ID=os.getenv('CHAT_ID','')
BOT_NAME=os.getenv('BOT_NAME','VISA-PRO')

CALENDARS={
    'Ashgabat':11,
    'Ashgabat VIP':12,
    'Ashgabat Student Visa':20
}

MONTHS_AHEAD=int(os.getenv('MONTHS_AHEAD','8'))
MAX_WORKERS=int(os.getenv('MAX_WORKERS','9'))

NORMAL_SLEEP_MIN=float(os.getenv('NORMAL_SLEEP_MIN','4'))
NORMAL_SLEEP_MAX=float(os.getenv('NORMAL_SLEEP_MAX','8'))
TURBO_SLEEP_MIN=float(os.getenv('TURBO_SLEEP_MIN','1.5'))
TURBO_SLEEP_MAX=float(os.getenv('TURBO_SLEEP_MAX','3'))

REQUEST_TIMEOUT=int(os.getenv('REQUEST_TIMEOUT','30'))

# ===== EMAIL =====
EMAIL_ENABLED=os.getenv('EMAIL_ENABLED','0')=='1'
SMTP_HOST=os.getenv('SMTP_HOST','smtp.gmail.com')
SMTP_PORT=int(os.getenv('SMTP_PORT','587'))
SMTP_USER=os.getenv('SMTP_USER','')
SMTP_PASSWORD=os.getenv('SMTP_PASSWORD','')
EMAIL_TO=os.getenv('EMAIL_TO','')

# ===== FILES =====
BASE_DIR=Path('./visa_pro_data')
BASE_DIR.mkdir(exist_ok=True)

STATE_FILE=BASE_DIR/'state.json'
HISTORY_FILE=BASE_DIR/'history.jsonl'

# ===== GLOBAL STATE =====
paused=False
turbo_until=0

last_alert_time_by_key={}
last_student_alert = {}   # 👈 PRO ANTI-SPAM

STUDENT_COOLDOWN=3600     # 1 hour

# ================= LOG =================

def log(x):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {x}")

# ================= TELEGRAM =================

def tg(method,data=None):
    if not TOKEN:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/{method}",
            data=data or {},
            timeout=20
        )
    except:
        pass

def send(msg):
    tg("sendMessage",{
        "chat_id":CHAT_ID,
        "text":msg
    })

# ================= FETCH =================

def fetch(url):
    try:
        r=requests.get(url,timeout=REQUEST_TIMEOUT)
        return r.text,r.status_code
    except Exception as e:
        return "",500

# ================= PARSER =================

def clean(html):
    html=re.sub(r'<[^>]+>',' ',html)
    return unescape(html)

def detect_slots(html):
    text=clean(html)
    found=re.findall(r'(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}).{0,200}?Available[^0-9]{0,10}(\d+)',text)
    slots=[]
    for d,c in found:
        try:
            count=int(c)
            if count>0:
                slots.append((d,count))
        except:
            pass
    return slots

def slot_type(name):
    n=name.lower()
    if "vip" in n:
        return "VIP"
    if "student" in n:
        return "STUDENT"
    return "STANDARD"

# ================= ALERT SYSTEM =================

def alert(result):
    global last_alert_time_by_key

    kind=slot_type(result["name"])
    now=time.time()

    slots=result["slots"]
    if not slots:
        return

    # ================= STUDENT PRO MODE =================
    if kind=="STUDENT":
        key=f"{result['name']}|{slots[0][0]}"

        if now-last_student_alert.get(key,0)<STUDENT_COOLDOWN:
            log("Student skipped (cooldown)")
            return

        last_student_alert[key]=now

    # ================= GLOBAL DEDUP =================
    key=f"{result['name']}|{slots[0][0]}"
    if now-last_alert_time_by_key.get(key,0)<3600:
        return

    last_alert_time_by_key[key]=now

    # ================= MESSAGE =================
    msg=f"🚨 {kind}\n{result['name']}\n\n"

    for d,c in slots[:10]:
        msg+=f"• {d} — {c}\n"

    msg+=f"\n👉 {result['url']}"

    send(msg)

# ================= CHECK =================

def check(name,cid):
    url=f"https://appointment.mosaicvisa.com/calendar/{cid}"
    html,code=fetch(url)

    if code!=200:
        return None

    slots=detect_slots(html)

    if slots:
        return {
            "name":name,
            "url":url,
            "slots":slots
        }

    return None

# ================= MAIN LOOP =================

def run():
    global paused

    send("🚀 VISA PRO STARTED")

    while True:
        if paused:
            time.sleep(3)
            continue

        tasks=[]
        for name,cid in CALENDARS.items():
            tasks.append((name,cid))

        results=[]

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futs=[ex.submit(check,n,c) for n,c in tasks]
            for f in as_completed(futs):
                r=f.result()
                if r:
                    results.append(r)

        for r in results:
            alert(r)

        sleep_time=random.uniform(NORMAL_SLEEP_MIN,NORMAL_SLEEP_MAX)
        log(f"sleep {sleep_time}")
        time.sleep(sleep_time)

# ================= START =================

if __name__=="__main__":
    run()
