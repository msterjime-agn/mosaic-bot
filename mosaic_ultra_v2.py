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
BOT_NAME=os.getenv('BOT_NAME','MOSAIC-PRO')

CALENDARS={
    'Ashgabat':11,
    'Ashgabat VIP':12,
    'Ashgabat Student Visa':20
}

MONTHS_AHEAD=int(os.getenv('MONTHS_AHEAD','8'))
MAX_WORKERS=int(os.getenv('MAX_WORKERS','9'))

NORMAL_SLEEP_MIN=float(os.getenv('NORMAL_SLEEP_MIN','4'))
NORMAL_SLEEP_MAX=float(os.getenv('NORMAL_SLEEP_MAX','8'))

REQUEST_TIMEOUT=int(os.getenv('REQUEST_TIMEOUT','30'))

# ================= ICONS =================
ICON_STUDENT="🟢"
ICON_STANDARD="🟡"
ICON_VIP="🔴"

# ================= GLOBAL STATE =================

paused=False
last_alert_time={}
student_cooldown={}
STUDENT_COOLDOWN=3600  # 1 hour

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
    except:
        return "",500

# ================= CLEAN =================

def clean_html(html):
    html=re.sub(r'<script.*?</script>',' ',html,flags=re.S)
    html=re.sub(r'<style.*?</style>',' ',html,flags=re.S)
    html=re.sub(r'<[^>]+>',' ',html)
    return unescape(html)

# ================= DATE PARSE =================

EN_MONTH={
    'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
    'july':7,'august':8,'september':9,'october':10,'november':11,'december':12,
    'jan':1,'feb':2,'mar':3,'apr':4,'jun':6,'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12
}

def parse_date(text):
    parts=text.strip().replace(',',' ').split()
    if len(parts)<2:
        return None

    try:
        d=int(parts[0])
    except:
        return None

    m=EN_MONTH.get(parts[1].lower())
    if not m:
        return None

    y=int(parts[2]) if len(parts)>2 and parts[2].isdigit() else date.today().year

    try:
        return date(y,m,d)
    except:
        return None

# ================= TRUE SLOT DETECTION =================

def parse_slots(html):
    text=clean_html(html)
    today=date.today()

    slots=[]
    seen=set()

    # TRUE detection: only date + available/reserved + number
    pattern=r'(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}).{0,200}?(Available|Reserved)[^0-9]{0,20}(\d+)'

    for day,status,count in re.findall(pattern,text,flags=re.I|re.S):

        if status.lower()=="reserved":
            continue

        try:
            count=int(count)
        except:
            continue

        if count<=0:
            continue

        dt=parse_date(day)
        if not dt or dt<today:
            continue

        key=(dt.isoformat(),count)

        if key in seen:
            continue

        seen.add(key)

        slots.append({
            "date":dt.isoformat(),
            "text":day,
            "count":count
        })

    return slots

# ================= TYPE =================

def slot_type(name):
    n=name.lower()
    if "vip" in n:
        return "VIP"
    if "student" in n:
        return "STUDENT"
    return "STANDARD"

# ================= ALERT =================

def alert(result):

    kind=slot_type(result["name"])
    slots=result["slots"]

    if not slots:
        return

    now=time.time()

    # ================= STUDENT PRO LIMIT =================
    if kind=="STUDENT":
        key=result["name"]

        if now - student_cooldown.get(key,0) < STUDENT_COOLDOWN:
            log("🟢 Student cooldown skip")
            return

        student_cooldown[key]=now

    # ================= GLOBAL DEDUP =================
    key=f"{result['name']}|{slots[0]['date']}"

    if now - last_alert_time.get(key,0) < 3600:
        return

    last_alert_time[key]=now

    # ================= ICON =================
    if kind=="VIP":
        icon=ICON_VIP
    elif kind=="STUDENT":
        icon=ICON_STUDENT
    else:
        icon=ICON_STANDARD

    # ================= MESSAGE =================

    msg=f"{icon} {kind} | SLOT FOUND\n"
    msg+=f"{result['name']}\n\n"

    for s in slots[:10]:
        msg+=f"• {s['date']} — {s['count']}\n"

    msg+=f"\n👉 {result['url']}"

    send(msg)

# ================= CHECK =================

def check(name,cid):
    url=f"https://appointment.mosaicvisa.com/calendar/{cid}"
    html,code=fetch(url)

    if code!=200:
        return None

    slots=parse_slots(html)

    if slots:
        return {
            "name":name,
            "url":url,
            "slots":slots
        }

    return None

# ================= MAIN =================

def run():

    send("🚀 MOSAIC PRO STARTED")

    while True:

        tasks=[(n,c) for n,c in CALENDARS.items()]

        results=[]

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures=[ex.submit(check,n,c) for n,c in tasks]

            for f in as_completed(futures):
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
