import os, time, re, json, random, threading, webbrowser
from pathlib import Path
from datetime import datetime, date
from html import unescape
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import smtplib
from email.message import EmailMessage

TOKEN=os.getenv('TOKEN','8574441866:AAEB-iMe93NyoyECEuVYkyDWONbkdyJub50')
CHAT_ID=os.getenv('CHAT_ID','-1003682526875')
BOT_NAME=os.getenv('BOT_NAME','MOSAIC-ULTRA-FINAL')
CALENDARS={'Ashgabat':11,'Ashgabat VIP':12,'Ashgabat Student Visa':20}
MONTHS_AHEAD=int(os.getenv('MONTHS_AHEAD','8'))
MAX_WORKERS=int(os.getenv('MAX_WORKERS','9'))
NORMAL_SLEEP_MIN=float(os.getenv('NORMAL_SLEEP_MIN','4'))
NORMAL_SLEEP_MAX=float(os.getenv('NORMAL_SLEEP_MAX','8'))
TURBO_SLEEP_MIN=float(os.getenv('TURBO_SLEEP_MIN','1.5'))
TURBO_SLEEP_MAX=float(os.getenv('TURBO_SLEEP_MAX','3'))
REQUEST_TIMEOUT=int(os.getenv('REQUEST_TIMEOUT','30'))
HEARTBEAT_INTERVAL=int(os.getenv('HEARTBEAT_INTERVAL','900'))
STATUS_INTERVAL=int(os.getenv('STATUS_INTERVAL','3600'))
ALERT_COOLDOWN=int(os.getenv('ALERT_COOLDOWN','600'))
ERROR_COOLDOWN=int(os.getenv('ERROR_COOLDOWN','1800'))
FLOOD_ALERT_COUNT=int(os.getenv('FLOOD_ALERT_COUNT','7'))
REPEAT_ALERT_COUNT=int(os.getenv('REPEAT_ALERT_COUNT','1'))
FLOOD_ALERT_DELAY=float(os.getenv('FLOOD_ALERT_DELAY','3'))
STUDENT_SMS_COUNT=int(os.getenv('STUDENT_SMS_COUNT','2'))
STANDARD_SMS_COUNT=int(os.getenv('STANDARD_SMS_COUNT','5'))
VIP_SMS_COUNT=int(os.getenv('VIP_SMS_COUNT','12'))
EMAIL_ENABLED=os.getenv('EMAIL_ENABLED','0')=='1'
EMAIL_ON_VIP=os.getenv('EMAIL_ON_VIP','1')=='1'
EMAIL_ON_STANDARD=os.getenv('EMAIL_ON_STANDARD','0')=='1'
SMTP_HOST=os.getenv('SMTP_HOST','smtp.gmail.com')
SMTP_PORT=int(os.getenv('SMTP_PORT','587'))
SMTP_USER=os.getenv('SMTP_USER','').strip()
SMTP_PASSWORD=os.getenv('SMTP_PASSWORD','').strip()
EMAIL_TO=os.getenv('EMAIL_TO','').strip()
AUTO_OPEN_BROWSER_ON_SLOT=os.getenv('AUTO_OPEN_BROWSER_ON_SLOT','1')=='1'
PRIORITY_ALERTS=os.getenv('PRIORITY_ALERTS','1')=='1'
VIP_POPUP=os.getenv('VIP_POPUP','1')=='1'
VIP_SOUND=os.getenv('VIP_SOUND','1')=='1'
VIP_OPEN_BROWSER=os.getenv('VIP_OPEN_BROWSER','1')=='1'
STANDARD_POPUP=os.getenv('STANDARD_POPUP','1')=='1'
STANDARD_SOUND=os.getenv('STANDARD_SOUND','1')=='1'
STANDARD_OPEN_BROWSER=os.getenv('STANDARD_OPEN_BROWSER','0')=='1'
STUDENT_OPEN_BROWSER=os.getenv('STUDENT_OPEN_BROWSER','0')=='1'
VIP_COOLDOWN=int(os.getenv('VIP_COOLDOWN','900'))
STANDARD_COOLDOWN=int(os.getenv('STANDARD_COOLDOWN','900'))
STUDENT_COOLDOWN=int(os.getenv('STUDENT_COOLDOWN','1800'))
SEND_HTML_ON_SLOT=os.getenv('SEND_HTML_ON_SLOT','1')=='1'
ENABLE_COMMANDS=os.getenv('ENABLE_COMMANDS','1')=='1'
ENABLE_TURBO_AFTER_SLOT=os.getenv('ENABLE_TURBO_AFTER_SLOT','1')=='1'
TURBO_SECONDS_AFTER_SLOT=int(os.getenv('TURBO_SECONDS_AFTER_SLOT','300'))
PROXY_URL=os.getenv('PROXY_URL','').strip()
PROXIES={'http':PROXY_URL,'https':PROXY_URL} if PROXY_URL else None
BASE_DIR=Path('./mosaic_bot_data'); BASE_DIR.mkdir(parents=True,exist_ok=True)
LOG_FILE=BASE_DIR/'mosaic_ultra.log'; STATE_FILE=BASE_DIR/'mosaic_ultra_state.json'; HISTORY_FILE=BASE_DIR/'mosaic_slot_history.jsonl'
SNAP_DIR=BASE_DIR/'mosaic_snaps'; SNAP_DIR.mkdir(parents=True,exist_ok=True)
last_heartbeat_time=0; last_status_time=0; last_update_id=None; paused=False; turbo_until=0
last_alert_time_by_key={}; last_error_time_by_key={}
MONTH_NAMES_RU={1:'Январь',2:'Февраль',3:'Март',4:'Апрель',5:'Май',6:'Июнь',7:'Июль',8:'Август',9:'Сентябрь',10:'Октябрь',11:'Ноябрь',12:'Декабрь'}
EN_MONTH_TO_NUM={'january':1,'jan':1,'february':2,'feb':2,'march':3,'mar':3,'april':4,'apr':4,'may':5,'june':6,'jun':6,'july':7,'jul':7,'august':8,'aug':8,'september':9,'sep':9,'sept':9,'october':10,'oct':10,'november':11,'nov':11,'december':12,'dec':12}

def log(text):
    line=f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}"; print(line,flush=True)
    try: LOG_FILE.open('a',encoding='utf-8').write(line+'\n')
    except Exception: pass

def tg(method,data=None,files=None,timeout=30):
    try:
        r=requests.post(f'https://api.telegram.org/bot{TOKEN}/{method}',data=data or {},files=files,timeout=timeout,proxies=PROXIES)
        log(f'TG {method}: {r.status_code} {r.text[:250]}'); return r
    except Exception as e: log(f'TG ERROR {method}: {e}'); return None

def send_message(text,silent=False):
    r=tg('sendMessage',{'chat_id':CHAT_ID,'text':text,'disable_notification':silent}); return bool(r and r.ok)

def send_document(path,caption=''):
    try:
        with open(path,'rb') as f: r=tg('sendDocument',{'chat_id':CHAT_ID,'caption':caption},{'document':f},60)
        return bool(r and r.ok)
    except Exception as e: log(f'SEND DOCUMENT ERROR: {e}'); return False

def send_email_alert(subject, body):
    if not EMAIL_ENABLED:
        return False
    if not SMTP_USER or not SMTP_PASSWORD or not EMAIL_TO:
        log('EMAIL SKIP: SMTP_USER / SMTP_PASSWORD / EMAIL_TO not configured')
        return False
    try:
        msg = EmailMessage()
        msg['From'] = SMTP_USER
        msg['To'] = EMAIL_TO
        msg['Subject'] = subject
        msg.set_content(body)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)
        log(f'EMAIL SENT: {subject} -> {EMAIL_TO}')
        return True
    except Exception as e:
        log(f'EMAIL ERROR: {e}')
        return False

def load_state():
    try: return json.loads(STATE_FILE.read_text(encoding='utf-8')) if STATE_FILE.exists() else {'seen_slots':{},'last_stats':{},'last_circle_time':''}
    except Exception: return {'seen_slots':{},'last_stats':{},'last_circle_time':''}

def save_state(state):
    try: STATE_FILE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    except Exception as e: log(f'STATE SAVE ERROR: {e}')

def append_history(item):
    try: HISTORY_FILE.open('a',encoding='utf-8').write(json.dumps(item,ensure_ascii=False)+'\n')
    except Exception as e: log(f'HISTORY ERROR: {e}')

def month_add(y,m,add):
    total=y*12+(m-1)+add; return total//12,total%12+1

def months_to_check():
    today=date.today(); out=[]
    for i in range(MONTHS_AHEAD):
        y,m=month_add(today.year,today.month,i); out.append((f'{y}-{m:02d}',f'{MONTH_NAMES_RU[m]} {y}',y,m))
    return out

def make_url(cid,mv): return f'https://appointment.mosaicvisa.com/calendar/{cid}?month={mv}'

def fetch(url):
    headers={'User-Agent':random.choice(['Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/136 Safari/537.36','Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0','Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/18.3 Safari/605.1.15','Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/135 Safari/537.36']),'Cache-Control':'no-cache','Pragma':'no-cache','Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8','Accept-Language':'ru-RU,ru;q=0.9,en;q=0.8,tr;q=0.7'}
    err=None
    for i in range(3):
        try:
            r=requests.get(url,headers=headers,timeout=REQUEST_TIMEOUT,proxies=PROXIES); return r.text,r.status_code
        except Exception as e: err=e; log(f'FETCH RETRY {i+1}/3 {url}: {e}'); time.sleep(random.uniform(1.5,4))
    raise err

def clean_html(html):
    text=re.sub(r'<script\b[^>]*>.*?</script>',' ',html,flags=re.I|re.S); text=re.sub(r'<style\b[^>]*>.*?</style>',' ',text,flags=re.I|re.S)
    text=re.sub(r'<[^>]+>',' ',text); text=unescape(text); return re.sub(r'\s+',' ',text).strip()

def parse_date_text(day_text,year_hint):
    parts=day_text.strip().replace(',',' ').split()
    if len(parts)<2: return None
    try: d=int(parts[0])
    except Exception: return None
    m=EN_MONTH_TO_NUM.get(parts[1].lower())
    if not m: return None
    y=year_hint
    if len(parts)>=3:
        try: y=int(parts[2])
        except Exception: pass
    try: return date(y,m,d)
    except Exception: return None

def parse_slots(html,year_hint):
    text=clean_html(html); today=date.today(); entries=[]; seen=set()
    patterns=[r'(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}).{0,180}?Available[^0-9]{0,25}([0-9]+)',r'(\d{1,2}\s+[A-Za-z]{3,9}).{0,180}?Available[^0-9]{0,25}([0-9]+)',r'Available[^0-9]{0,25}([0-9]+).{0,180}?(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})',r'Available[^0-9]{0,25}([0-9]+).{0,180}?(\d{1,2}\s+[A-Za-z]{3,9})']
    for p in patterns:
        for match in re.findall(p,text,flags=re.I|re.S):
            count_text,day_text=(match[0],match[1]) if str(match[0]).isdigit() else (match[1],match[0])
            try: count=int(count_text)
            except Exception: continue
            dt=parse_date_text(day_text,year_hint)
            if not dt or dt<today: continue
            key=(dt.isoformat(),count)
            if key in seen: continue
            seen.add(key)
            if count>0: entries.append({'date':dt.isoformat(),'text':day_text.strip(),'count':count})
    entries.sort(key=lambda x:x['date']); return entries,text

def detect_state(html,year_hint):
    text=clean_html(html); low=text.lower(); slots,_=parse_slots(html,year_hint)
    if slots: return 'SLOTS_FOUND',slots,text
    if re.search(r'Reserved[^0-9]{0,25}0',text,flags=re.I) or re.search(r'Available[^0-9]{0,25}0',text,flags=re.I) or re.search(r'\b\d{1,2}\s+[A-Za-z]{3,9}\b',text): return 'ZERO_SLOTS',[],text
    if any(w in low for w in ['calendar','reserved','available','next','previous']): return 'EMPTY_MONTH',[],text
    return 'UNKNOWN',[],text

def save_snapshot(prefix,html):
    path=SNAP_DIR/(re.sub(r'[^A-Za-z0-9_-]+','_',prefix)+'_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.html')
    try: path.write_text(html,encoding='utf-8',errors='ignore'); return str(path)
    except Exception as e: log(f'SNAP ERROR: {e}'); return ''

def check_one(task):
    name,cid,mv,mt,y=task; url=make_url(cid,mv); key=f'{name} / {mt}'
    try:
        html,status=fetch(url)
        if status!=200: return {'ok':False,'state':'HTTP_ERROR','key':key,'url':url,'error':f'HTTP {status}','slots':[],'calendar_name':name,'month_title':mt,'month_value':mv}
        st,slots,text=detect_state(html,y); snap=save_snapshot(f'{name}_{mv}_{st}',html) if st in ('SLOTS_FOUND','UNKNOWN') else ''
        return {'ok':st!='UNKNOWN','state':st,'key':key,'url':url,'error':'','slots':slots,'snapshot':snap,'calendar_name':name,'month_title':mt,'month_value':mv}
    except Exception as e: return {'ok':False,'state':'ERROR','key':key,'url':url,'error':str(e),'slots':[],'calendar_name':name,'month_title':mt,'month_value':mv}

def build_tasks():
    tasks=[]
    for mv,mt,y,_ in months_to_check():
        for name,cid in CALENDARS.items(): tasks.append((name,cid,mv,mt,y))
    random.shuffle(tasks); return tasks

def is_new_slot_event(state,result):
    seen=state.setdefault('seen_slots',{}); old=set(seen.get(result['key'],[])); cur=set(f"{x['date']}:{x['count']}" for x in result['slots'])
    new=cur-old; seen[result['key']]=sorted(cur); save_state(state); return bool(new),new


def calendar_kind(name):
    low=(name or '').lower()
    if 'vip' in low:
        return 'VIP'
    if 'student' in low:
        return 'STUDENT'
    return 'STANDARD'

def priority_settings(kind):
    if kind=='VIP':
        return {'label':'🔴🔴🔴 VIP SLOT FOUND','telegram_prefix':'🔴 VIP','popup':VIP_POPUP,'sound':VIP_SOUND,'open_browser':VIP_OPEN_BROWSER,'cooldown':VIP_COOLDOWN,'flood':VIP_SMS_COUNT}
    if kind=='STANDARD':
        return {'label':'🟡 STANDARD SLOT FOUND','telegram_prefix':'🟡 STANDARD','popup':STANDARD_POPUP,'sound':STANDARD_SOUND,'open_browser':STANDARD_OPEN_BROWSER,'cooldown':STANDARD_COOLDOWN,'flood':STANDARD_SMS_COUNT}
    return {'label':'🟢 STUDENT SLOT FOUND','telegram_prefix':'🟢 STUDENT','popup':False,'sound':False,'open_browser':STUDENT_OPEN_BROWSER,'cooldown':STUDENT_COOLDOWN,'flood':STUDENT_SMS_COUNT}

def alert_sound(kind):
    if os.name!='nt':
        return
    try:
        import winsound
        if kind=='VIP':
            for _ in range(5):
                winsound.Beep(1200,350)
                winsound.Beep(900,250)
        elif kind=='STANDARD':
            winsound.Beep(900,300)
            winsound.Beep(900,300)
    except Exception as e:
        log(f'SOUND ERROR: {e}')

def alert_popup(kind,text):
    if os.name!='nt':
        return
    def worker():
        try:
            import tkinter as tk
            from tkinter import messagebox
            root=tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            title='🔴 VIP SLOT FOUND' if kind=='VIP' else '🟡 STANDARD SLOT FOUND'
            messagebox.showwarning(title,text,parent=root)
            root.destroy()
        except Exception as e:
            log(f'POPUP ERROR: {e}')
    try:
        threading.Thread(target=worker,daemon=True).start()
    except Exception as e:
        log(f'POPUP THREAD ERROR: {e}')


def alert_slots(result,state):
    global turbo_until
    now=time.time()
    kind=calendar_kind(result['calendar_name'])
    settings=priority_settings(kind)
    slots=result.get('slots') or []
    if not slots:
        return

    first_slot=slots[0]
    date_key=first_slot.get('date','')
    key=f"{kind}:{result['calendar_name']}:{result['month_value']}:{date_key}"

    if now-last_alert_time_by_key.get(key,0)<settings['cooldown']:
        log(f'[{key}] PRIORITY ALERT COOLDOWN')
        return

    changed,_=is_new_slot_event(state,result)
    repeat_alert=not changed

    if repeat_alert:
        log(f'[{key}] SAME SLOT ALREADY SEEN, REPEAT ALERT')

    lines=[]
    for item in slots[:15]:
        lines.append(f"• {datetime.fromisoformat(item['date']).strftime('%d.%m.%Y')} — {item['count']}")

    title='⏰ СЛОТЫ ВСЁ ЕЩЁ ОТКРЫТЫ' if repeat_alert else settings['label']

    msg=(f"{settings['telegram_prefix']} | {title} [{BOT_NAME}]\n"
         f"🏷 {result['calendar_name']}\n"
         f"📅 {result['month_title']}\n"
         f"📍 Ближайшая дата: {datetime.fromisoformat(slots[0]['date']).strftime('%d.%m.%Y')}\n"
         f"Всего дней с местами: {len(slots)}\n"
         + '\n'.join(lines)
         + f"\n👉 {result['url']}")

    append_history({'time':datetime.now().isoformat(timespec='seconds'),'calendar':result['calendar_name'],'priority':kind,'month':result['month_title'],'url':result['url'],'slots':slots,'snapshot':result.get('snapshot','')})

    if settings['sound'] and not repeat_alert:
        threading.Thread(target=alert_sound,args=(kind,),daemon=True).start()

    if settings['popup'] and not repeat_alert:
        popup_text=(f"{settings['label']}\n\n"
                    f"{result['calendar_name']}\n"
                    f"Ближайшая дата: {datetime.fromisoformat(slots[0]['date']).strftime('%d.%m.%Y')}\n"
                    f"Мест: {slots[0]['count']}\n\n"
                    f"{result['url']}")
        alert_popup(kind,popup_text)

    if settings['open_browser'] and AUTO_OPEN_BROWSER_ON_SLOT:
        try:
            webbrowser.open(result['url'])
        except Exception as e:
            log(f'BROWSER OPEN ERROR: {e}')

    if ENABLE_TURBO_AFTER_SLOT:
        turbo_until=time.time()+TURBO_SECONDS_AFTER_SLOT

    alert_count=REPEAT_ALERT_COUNT if repeat_alert else settings['flood']

    if (not repeat_alert) and EMAIL_ENABLED:
        if ('vip' in visa_text and EMAIL_ON_VIP) or ('vip' not in visa_text and 'student' not in visa_text and EMAIL_ON_STANDARD):
            email_subject = f"{visa_type} SLOT FOUND - {result['calendar_name']}"
            email_body = msg.replace('\n👉 ', '\n\nLink: ')
            if send_email_alert(email_subject, email_body):
                log('EMAIL ALERT SENT')

    for i in range(alert_count):
        send_message(msg,False)
        if i+1<alert_count:
            time.sleep(FLOOD_ALERT_DELAY)

    if SEND_HTML_ON_SLOT and result.get('snapshot') and kind in ('VIP','STANDARD'):
        send_document(result['snapshot'],f'HTML snapshot {kind} слота')

    last_alert_time_by_key[key]=now

def alert_error_once(result):
    now=time.time(); key=result['key']
    if now-last_error_time_by_key.get(key,0)<ERROR_COOLDOWN: return
    if send_message(f"⚠️ ОШИБКА [{BOT_NAME}]\n{key}\n{result.get('error','')[:700]}\n{result.get('url','')}",False): last_error_time_by_key[key]=now

def last_history(limit=5):
    if not HISTORY_FILE.exists(): return 'Истории слотов пока нет.'
    out=[]
    for line in HISTORY_FILE.read_text(encoding='utf-8',errors='ignore').splitlines()[-limit:]:
        try:
            x=json.loads(line); out.append(f"{x.get('time')} | {x.get('calendar')} | {x.get('month')} | {x.get('url')}")
        except Exception: pass
    return '\n'.join(out) or 'Истории слотов пока нет.'

def send_heartbeat(stats):
    global last_heartbeat_time
    now=time.time()
    if now-last_heartbeat_time<HEARTBEAT_INTERVAL: return
    msg=f"🟢 ONLINE [{BOT_NAME}]\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n🔎 Проверок за круг: {sum(stats.values())}\n0️⃣ Без мест: {stats.get('ZERO_SLOTS',0)}\n⬜ Пустые месяцы: {stats.get('EMPTY_MONTH',0)}\n🔥 Слоты: {stats.get('SLOTS_FOUND',0)}\n⚠️ Ошибки: {stats.get('ERROR',0)+stats.get('HTTP_ERROR',0)+stats.get('UNKNOWN',0)}"
    if send_message(msg,True): last_heartbeat_time=now

def send_hourly_status(stats):
    global last_status_time
    now=time.time()
    if now-last_status_time<STATUS_INTERVAL: return
    msg=f"ℹ️ STATUS [{BOT_NAME}]\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n🔥 Со слотами: {stats.get('SLOTS_FOUND',0)}\n0️⃣ Дни есть, мест нет: {stats.get('ZERO_SLOTS',0)}\n⬜ Пустые месяцы: {stats.get('EMPTY_MONTH',0)}\n⚠️ Ошибки/unknown: {stats.get('ERROR',0)+stats.get('HTTP_ERROR',0)+stats.get('UNKNOWN',0)}\n🤖 Бот работает"
    if send_message(msg,True): last_status_time=now

def make_test_result(kind):
    today_iso = date.today().isoformat()
    if kind == 'VIP':
        return {'calendar_name':'Ashgabat VIP','month_title':'TEST MONTH','month_value':'TEST','url':'https://appointment.mosaicvisa.com/calendar/12?month=TEST','slots':[{'date':today_iso,'text':'TEST VIP','count':12}],'snapshot':'','key':'Ashgabat VIP / TEST MONTH'}
    if kind == 'STANDARD':
        return {'calendar_name':'Ashgabat','month_title':'TEST MONTH','month_value':'TEST','url':'https://appointment.mosaicvisa.com/calendar/11?month=TEST','slots':[{'date':today_iso,'text':'TEST STANDARD','count':8}],'snapshot':'','key':'Ashgabat / TEST MONTH'}
    return {'calendar_name':'Ashgabat Student Visa','month_title':'TEST MONTH','month_value':'TEST','url':'https://appointment.mosaicvisa.com/calendar/20?month=TEST','slots':[{'date':today_iso,'text':'TEST STUDENT','count':30}],'snapshot':'','key':'Ashgabat Student Visa / TEST MONTH'}

def command_text():
    return 'Команды:\n/status — статус\n/pause — пауза\n/resume — продолжить\n/months — месяцы проверки\n/history — последние найденные слоты\n/turbo — ускорить на 5 минут\n/testvip — тест VIP 12 Telegram + Email + браузер\n/teststandard — тест Standard 5 Telegram\n/teststudent — тест Student 2 Telegram\n/help — команды'

def handle_command(text,state):
    global paused, turbo_until
    cmd = text.strip().split()[0].lower()

    if cmd == '/pause':
        paused = True
        send_message('⏸ Бот поставлен на паузу.')

    elif cmd == '/resume':
        paused = False
        send_message('▶️ Бот продолжает проверку.')

    elif cmd == '/months':
        send_message('📅 Проверяемые месяцы:\n' + '\n'.join([m[1] for m in months_to_check()]))

    elif cmd == '/history':
        send_message('📊 Последние слоты:\n' + last_history())

    elif cmd == '/turbo':
        turbo_until = time.time() + TURBO_SECONDS_AFTER_SLOT
        send_message(f'🔥 TURBO включён на {TURBO_SECONDS_AFTER_SLOT} сек.')

    elif cmd == '/testvip':
        send_message('🧪 TEST VIP: 12 Telegram + Email + браузер', False)
        alert_slots(make_test_result('VIP'), state)

    elif cmd == '/teststandard':
        send_message('🧪 TEST STANDARD: 5 Telegram', False)
        alert_slots(make_test_result('STANDARD'), state)

    elif cmd == '/teststudent':
        send_message('🧪 TEST STUDENT: 2 Telegram', False)
        alert_slots(make_test_result('STUDENT'), state)

    elif cmd == '/status':
        st = state.get('last_stats', {})
        send_message(
            f"ℹ️ STATUS NOW [{BOT_NAME}]\n"
            f"Пауза: {'да' if paused else 'нет'}\n"
            f"Turbo: {'да' if time.time() < turbo_until else 'нет'}\n"
            f"Последний круг: {state.get('last_circle_time','-')}\n"
            f"Проверок: {sum(st.values())}\n"
            f"Слоты: {st.get('SLOTS_FOUND',0)}\n"
            f"Без мест: {st.get('ZERO_SLOTS',0)}\n"
            f"Пустые: {st.get('EMPTY_MONTH',0)}\n"
            f"Ошибки: {st.get('ERROR',0)+st.get('HTTP_ERROR',0)+st.get('UNKNOWN',0)}"
        )

    elif cmd == '/help':
        send_message(command_text())

def command_loop(state):
    global last_update_id
    log('COMMAND LOOP STARTED')
    while True:
        try:
            data={'timeout':20}
            if last_update_id is not None: data['offset']=last_update_id+1
            r=requests.post(f'https://api.telegram.org/bot{TOKEN}/getUpdates',data=data,timeout=30,proxies=PROXIES)
            if not r.ok: time.sleep(5); continue
            for upd in r.json().get('result',[]):
                last_update_id=upd.get('update_id',last_update_id); msg=upd.get('message') or upd.get('edited_message') or {}; chat=msg.get('chat',{}); text=msg.get('text','')
                if str(chat.get('id'))==str(CHAT_ID) and text.startswith('/'): handle_command(text,state)
        except Exception as e: log(f'COMMAND LOOP ERROR: {e}'); time.sleep(5)

def main():
    global turbo_until
    log(f'🚀 BOT START {BOT_NAME}'); send_message(f'✅ ULTRA FINAL режим: бот запущен ({BOT_NAME})\n🔴 VIP: {VIP_SMS_COUNT} Telegram + Email + браузер\n🟡 Standard: {STANDARD_SMS_COUNT} Telegram\n🟢 Student: {STUDENT_SMS_COUNT} Telegram\nEmail: {"вкл" if EMAIL_ENABLED else "выкл"}\n{command_text()}',False)
    state=load_state()
    if ENABLE_COMMANDS: threading.Thread(target=command_loop,args=(state,),daemon=True).start()
    while True:
        if paused: log('PAUSED'); time.sleep(5); continue
        tasks=build_tasks(); stats={}; log(f'TASKS: {len(tasks)} | MONTHS_AHEAD={MONTHS_AHEAD} | WORKERS={MAX_WORKERS}')
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            for fut in as_completed({ex.submit(check_one,t):t for t in tasks}):
                result=fut.result(); st=result['state']; stats[st]=stats.get(st,0)+1
                if st=='SLOTS_FOUND': log(f"[{result['key']}] SLOTS: {result['slots']}"); alert_slots(result,state)
                elif st in ('ERROR','HTTP_ERROR'): log(f"[{result['key']}] {st}: {result.get('error','')}"); alert_error_once(result)
                elif st=='UNKNOWN': log(f"[{result['key']}] UNKNOWN PAGE, SNAP={result.get('snapshot','')}")
                else: log(f"[{result['key']}] {st}")
                time.sleep(random.uniform(0.05,0.25))
        state['last_stats']=stats; state['last_circle_time']=datetime.now().strftime('%d.%m.%Y %H:%M:%S'); save_state(state)
        send_heartbeat(stats); send_hourly_status(stats)
        if time.time()<turbo_until: sl=random.uniform(TURBO_SLEEP_MIN,TURBO_SLEEP_MAX); log(f'TURBO SLEEP: {round(sl,1)} sec')
        else: sl=random.uniform(NORMAL_SLEEP_MIN,NORMAL_SLEEP_MAX); log(f'SLEEP: {round(sl,1)} sec')
        time.sleep(sl)

if __name__=='__main__': main()
