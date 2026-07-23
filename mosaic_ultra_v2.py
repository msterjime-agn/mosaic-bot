import os, time, re, json, random, threading, webbrowser
from pathlib import Path
from datetime import datetime, date
from html import unescape
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

TOKEN=os.getenv('TOKEN','8574441866:AAHnn3FdSMoqWQblo66P8zc9k_I_OVyHw2Q')
CHAT_ID=os.getenv('CHAT_ID','-1003682526875')
BOT_NAME=os.getenv('BOT_NAME','MOSAIC-ULTRA')
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
FLOOD_ALERT_DELAY=float(os.getenv('FLOOD_ALERT_DELAY','3'))
STUDENT_SMS_COUNT=int(os.getenv('STUDENT_SMS_COUNT','2'))
STANDARD_SMS_COUNT=int(os.getenv('STANDARD_SMS_COUNT','5'))
VIP_SMS_COUNT=int(os.getenv('VIP_SMS_COUNT','12'))
CONFIRM_BEFORE_ALERT=os.getenv('CONFIRM_BEFORE_ALERT','1')=='1'
MAX_SLOT_COUNT=int(os.getenv('MAX_SLOT_COUNT','2000'))  # аварийный предел; настоящий фильтр — кликабельность дня
SIGNAL_ON_RESERVED=os.getenv('SIGNAL_ON_RESERVED','1')=='1'   # сигналить, когда меняется 'занято' (движение брони)
SIGNAL_HOT_COOLDOWN=int(os.getenv('SIGNAL_HOT_COOLDOWN','120'))  # для важных сигналов (месяц открыли/дни добавили)
SIGNAL_COOLDOWN=int(os.getenv('SIGNAL_COOLDOWN','900'))
MIN_CHANGE_ALERT_GAP=int(os.getenv('MIN_CHANGE_ALERT_GAP','60'))
AUTO_OPEN_BROWSER_ON_SLOT=os.getenv('AUTO_OPEN_BROWSER_ON_SLOT','1')=='1'
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
last_alert_time_by_key={}; last_error_time_by_key={}; last_signal_time_by_key={}; last_change_alert_time_by_key={}
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

def load_state():
    default={'seen_slots':{},'last_stats':{},'last_circle_time':'','slot_map':{},'page_states':{},'last_change_time':''}
    try:
        if not STATE_FILE.exists(): return default
        state=json.loads(STATE_FILE.read_text(encoding='utf-8'))
        for k,v in default.items(): state.setdefault(k,v)
        return state
    except Exception: return default

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

BASE_SITE='https://appointment.mosaicvisa.com'

def _abs_url(href):
    href=(href or '').strip()
    if not href: return ''
    if href.startswith('http'): return href
    if href.startswith('/'): return BASE_SITE+href
    return BASE_SITE+'/'+href

def extract_day_links(html):
    """Пытаемся достать ПРЯМУЮ ссылку на конкретный день из HTML.
    Ищем href/data-атрибуты, содержащие дату в формате YYYY-MM-DD."""
    links={}
    try:
        for m in re.finditer(r'href\s*=\s*["\']([^"\']*?(\d{4}-\d{2}-\d{2})[^"\']*)["\']', html, flags=re.I):
            links[m.group(2)]=_abs_url(m.group(1))
        for m in re.finditer(r'data-(?:date|day)\s*=\s*["\'](\d{4}-\d{2}-\d{2})["\'][^>]{0,200}?href\s*=\s*["\']([^"\']+)["\']', html, flags=re.I|re.S):
            links.setdefault(m.group(1), _abs_url(m.group(2)))
    except Exception as e:
        log(f'LINK PARSE ERROR: {e}')
    return links

def _find_date_tokens(text):
    out=[]
    for m in re.finditer(r'\b(\d{1,2})\s+([A-Za-z]{3,9})(?:\s+(\d{4}))?\b', text):
        if m.group(2).lower() in EN_MONTH_TO_NUM: out.append((m.start(), m.end(), m.group(0)))
    return out

def parse_calendar_rows(html):
    """Полный слепок календаря: по каждому дню — свободно (data-remaining),
    занято (Reserved N из ячейки) и кликабельность. Нужен для РАННИХ СИГНАЛОВ:
    видно, как админы готовят месяц ещё до появления свободных мест."""
    out={}
    for m in re.finditer(r'<tr\b([^>]*)>(.*?)</tr>', html, flags=re.I|re.S):
        tag,body=m.group(1),m.group(2)
        if 'calendar-dates' not in tag: continue
        dm=re.search(r'data-date\s*=\s*"([^"]*)"', tag)
        iso=(dm.group(1) if dm else '').strip()
        if not iso: continue
        rm=re.search(r'data-remaining\s*=\s*"(\d+)"', tag)
        rem=int(rm.group(1)) if rm else 0
        txt=re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',body)).strip()
        vr=re.search(r'Reserved[^0-9]{0,20}(\d+)', txt, flags=re.I)
        resv=int(vr.group(1)) if vr else None
        out[iso]={'r':rem,'v':resv,'c':('cursor: pointer' in tag.lower())}
    return out

def parse_slots(html,year_hint,label_ctx=''):
    """ТОЧНЫЙ парсинг календаря Mosaic по атрибутам строки таблицы:
        <tr data-date-formatted="28.07.2026" data-date="2026-07-28" data-remaining="1"
            class="calendar-dates" style="cursor: pointer...">
            <td>28 July 2026</td><td>Available 1</td></tr>

    ВАЖНО: свободные места = data-remaining.
    В видимой ячейке сайт пишет "Reserved N" — это СКОЛЬКО ЗАНЯТО.
    Старая версия читала это "Reserved" и слала фантомы (229 мест при нуле на сайте).
    """
    today=date.today(); res={}; hidden={}; rows_seen=0
    for m in re.finditer(r'<tr\b[^>]*>', html, flags=re.I|re.S):
        tag=m.group(0)
        if 'calendar-dates' not in tag: continue
        rows_seen+=1
        dm=re.search(r'data-date\s*=\s*"(\d{4}-\d{2}-\d{2})"', tag)
        rm=re.search(r'data-remaining\s*=\s*"(\d+)"', tag)
        if not dm or not rm: continue
        iso=dm.group(1)
        try: cnt=int(rm.group(1))
        except Exception: continue
        try: dt=date.fromisoformat(iso)
        except Exception: continue
        # ГЛАВНОЕ ПРАВИЛО (из кода самого сайта):
        #   if(remaining === 0) return false;
        # то есть ЛЮБОЙ день с data-remaining > 0 доступен для записи.
        # Стиль курсора — только оформление, фильтровать по нему НЕЛЬЗЯ
        # (проверено: 24.08.2026 с 285 местами открывается и форма заполняется).
        if dt<today or cnt<=0: continue
        clickable=('cursor: pointer' in tag.lower())
        fm=re.search(r'data-date-formatted\s*=\s*"([^"]*)"', tag)
        label=(fm.group(1) if fm else iso)
        if cnt>MAX_SLOT_COUNT:
            log(f'BÜYÜK AÇILIŞ [{label_ctx or "?"}] {iso}: {cnt} yer — bildiriyorum')
        res[iso]={'date':iso,'text':label,'count':cnt,'clickable':clickable}
    parse_slots.last_hidden=hidden
    if rows_seen:
        entries=sorted(res.values(), key=lambda x:x['date'])
        return entries, clean_html(html)
    # запасной вариант: разметка сайта изменилась — разбираем текстом по блокам дней
    log(f'CALENDAR ROWS NOT FOUND [{label_ctx or "?"}] — запасной текстовый парсер')
    return _parse_slots_text(html,year_hint), clean_html(html)

def _find_date_tokens(text):
    out=[]
    for m in re.finditer(r'\b(\d{1,2})\s+([A-Za-z]{3,9})(?:\s+(\d{4}))?\b', text):
        if m.group(2).lower() in EN_MONTH_TO_NUM: out.append((m.start(), m.end(), m.group(0)))
    return out

def _parse_slots_text(html,year_hint):
    """Запасной парсер (если сайт сменит разметку). Ищет ТОЛЬКО слово Available,
    блоками по дням, чтобы не цеплять число соседнего дня и не путать с Reserved."""
    text=clean_html(html); today=date.today()
    toks=_find_date_tokens(text)
    if not toks: return []
    avail_re=re.compile(r'\bAvailable\b[^0-9]{0,25}(\d+)', flags=re.I)
    LIMIT=200
    def seg_after(i):
        s=toks[i][1]; e=toks[i+1][0] if i+1<len(toks) else min(len(text), s+LIMIT)
        return text[s:min(e, s+LIMIT)]
    res={}
    for i,(s,e,dtxt) in enumerate(toks):
        dt=parse_date_text(dtxt,year_hint)
        if not dt or dt<today: continue
        m=avail_re.search(seg_after(i))
        if not m: continue
        iso=dt.isoformat()
        if iso in res: continue
        try: c=int(m.group(1))
        except Exception: continue
        if 0<c<=MAX_SLOT_COUNT: res[iso]={'date':iso,'text':dtxt.strip(),'count':c,'clickable':True}
    return sorted(res.values(), key=lambda x:x['date'])

def detect_state(html,year_hint,label_ctx=''):
    text=clean_html(html); low=text.lower(); slots,_=parse_slots(html,year_hint,label_ctx)
    if slots: return 'SLOTS_FOUND',slots,text
    if 'calendar-dates' in html: return 'ZERO_SLOTS',[],text
    if re.search(r'Reserved[^0-9]{0,25}\d',text,flags=re.I) or re.search(r'\b\d{1,2}\s+[A-Za-z]{3,9}\b',text): return 'ZERO_SLOTS',[],text
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
        st,slots,text=detect_state(html,y,key); snap=save_snapshot(f'{name}_{mv}_{st}',html) if st in ('SLOTS_FOUND','UNKNOWN') else ''
        day_links=extract_day_links(html) if st=='SLOTS_FOUND' else {}
        cal=parse_calendar_rows(html)
        hidden=getattr(parse_slots,'last_hidden',{}) or {}
        return {'ok':st!='UNKNOWN','state':st,'key':key,'url':url,'error':'','slots':slots,'snapshot':snap,'day_links':day_links,'cal':cal,'hidden':hidden,'calendar_name':name,'month_title':mt,'month_value':mv}
    except Exception as e: return {'ok':False,'state':'ERROR','key':key,'url':url,'error':str(e),'slots':[],'calendar_name':name,'month_title':mt,'month_value':mv}

def build_tasks():
    tasks=[]
    for mv,mt,y,_ in months_to_check():
        for name,cid in CALENDARS.items(): tasks.append((name,cid,mv,mt,y))
    random.shuffle(tasks); return tasks

def is_new_slot_event(state,result):
    seen=state.setdefault('seen_slots',{}); old=set(seen.get(result['key'],[])); cur=set(f"{x['date']}:{x['count']}" for x in result['slots'])
    new=cur-old; seen[result['key']]=sorted(cur); save_state(state); return bool(new),new

def tier_of(calendar_name):
    n=calendar_name.lower()
    if 'student' in n: return '🟢','STUDENT',STUDENT_SMS_COUNT
    if 'vip' in n: return '🔴','VIP',VIP_SMS_COUNT
    return '🟡','STANDARD',STANDARD_SMS_COUNT

def fmt_date(iso):
    try: return datetime.fromisoformat(iso).strftime('%d.%m.%Y')
    except Exception: return iso

def mark_changed(state):
    state['last_change_time']=datetime.now().strftime('%d.%m.%Y %H:%M:%S')

def smart_diff(state,result,commit=True):
    """Сравнивает текущие слоты с последним известным состоянием по этому календарю+месяцу.
    Возвращает (новые_даты, изменённые_количества, исчезнувшие_даты).
    commit=False — только посмотреть, не записывая (чтобы подавленный алерт не потерялся)."""
    slot_map=state.setdefault('slot_map',{}); key=result['key']
    old=slot_map.get(key)
    if old is None:
        old={}
        for s in state.get('seen_slots',{}).get(key,[]):
            try: d,c=s.rsplit(':',1); old[d]=int(c)
            except Exception: pass
    cur={x['date']:x['count'] for x in result['slots']}
    new_dates={d:c for d,c in cur.items() if d not in old}
    changed={d:(old[d],c) for d,c in cur.items() if d in old and old[d]!=c}
    removed={d:c for d,c in old.items() if d not in cur}
    if commit:
        slot_map[key]=cur
        state.setdefault('seen_slots',{})[key]=sorted(f'{d}:{c}' for d,c in cur.items())
        if new_dates or changed or removed: mark_changed(state)
        save_state(state)
    return new_dates,changed,removed

def check_slots_gone(result,state):
    """Если раньше по этому ключу были места, а теперь страница без слотов — сообщаем один раз."""
    slot_map=state.setdefault('slot_map',{}); key=result['key']
    old=slot_map.get(key)
    if not old: return
    slot_map[key]={}
    state.setdefault('seen_slots',{})[key]=[]
    mark_changed(state); save_state(state)
    emoji,tier,_=tier_of(result['calendar_name'])
    lines=[f"❌ {fmt_date(d)} — было {c}, исчезло" for d,c in sorted(old.items())]
    send_message(f"{emoji} {tier} | СЛОТЫ ИСЧЕЗЛИ [{BOT_NAME}]\n🏷 {result['calendar_name']}\n📅 {result['month_title']}\n"+'\n'.join(lines)+f"\n👉 {result['url']}",False)

def early_signal(result,state):
    """РАННИЙ СИГНАЛ: ловим, что сайт 'зашевелился' — админы готовят месяц,
    подгружают календарь, двигают вместимость — ЕЩЁ ДО появления свободных мест.

    Сравниваем слепок календаря (по каждому дню: свободно / занято / кликабельность):
      • месяц был пустой → появились даты        = ГОТОВЯТ МЕСЯЦ   (важно)
      • стало больше активных дней               = ДОБАВЛЯЮТ ДНИ   (важно)
      • день стал кликабельным                   = ОТКРЫВАЮТ ДЕНЬ  (важно)
      • меняется 'Reserved' (занято)             = ИДЁТ ДВИЖЕНИЕ   (обычный)
    """
    key=result['key']; st=result['state']
    cur=result.get('cal') or {}
    fps=state.setdefault('cal_fp',{})
    prev=fps.get(key)
    # состояние страницы (грубое) — оставляем как было
    ps=state.setdefault('page_states',{}); prev_state=ps.get(key); ps[key]=st
    fps[key]=cur
    if prev is None:
        save_state(state); return               # первый круг — просто запоминаем
    if st in ('ERROR','HTTP_ERROR') or prev_state in ('ERROR','HTTP_ERROR'):
        save_state(state); return
    if st=='SLOTS_FOUND':
        save_state(state); return               # слоты есть — про них скажет alert_slots

    hot=[]; soft=[]
    # Дни с загруженной вместимостью, но ещё ЗАКРЫТЫЕ — сильный признак подготовки месяца
    hid=result.get('hidden') or {}
    prev_hid=state.setdefault('hidden_fp',{}).get(key,{})
    state['hidden_fp'][key]={d:v['count'] for d,v in hid.items()}
    for d in sorted(hid.keys()):
        c=hid[d]['count']; pc=prev_hid.get(d)
        if pc is None:
            hot.append(f"{fmt_date(d)}: загружено {c} мест, день пока ЗАКРЫТ")
        elif pc!=c:
            soft.append(f"{fmt_date(d)}: вместимость {pc} → {c} (день закрыт)")
    prev_days=set(prev.keys()); cur_days=set(cur.keys())
    added=cur_days-prev_days
    if not prev_days and cur_days:
        hot.append(f"месяц открыли: появилось дней в календаре — {len(cur_days)}")
    elif added:
        hot.append(f"добавили дней: {len(prev_days)} → {len(cur_days)}")
    for d in sorted(cur_days & prev_days):
        a,b=prev[d],cur[d]
        if (not a.get('c')) and b.get('c'):
            hot.append(f"{fmt_date(d)}: день стал доступен для выбора")
        if a.get('r',0)==0 and b.get('r',0)>0:
            hot.append(f"{fmt_date(d)}: появились места — {b['r']}")
        if SIGNAL_ON_RESERVED and a.get('v') is not None and b.get('v') is not None and a['v']!=b['v']:
            soft.append(f"{fmt_date(d)}: занято {a['v']} → {b['v']}")
    if not hot and not soft and prev_state==st:
        save_state(state); return
    now=time.time()
    cd = SIGNAL_HOT_COOLDOWN if hot else SIGNAL_COOLDOWN
    if now-last_signal_time_by_key.get(key,0)<cd:
        save_state(state); return
    last_signal_time_by_key[key]=now
    mark_changed(state); save_state(state)
    emoji,tier,_=tier_of(result['calendar_name'])
    lines=hot[:6]+soft[:6]
    if not lines and prev_state!=st: lines=[f"состояние страницы: {prev_state} → {st}"]
    head="🔥🟡 РАННИЙ СИГНАЛ" if hot else "🟡 MOSAIC SIGNAL"
    send_message(f"{head} [{BOT_NAME}]\n{emoji} {tier}\n🏷 {result['calendar_name']}\n📅 {result['month_title']}\n"
                 f"📊 Календарь зашевелился:\n   • "+"\n   • ".join(lines)+
                 f"\n👀 Записаться пока нельзя — сайт готовит месяц\n👉 {result['url']}", False)

def reverify(result):
    """Повторно открываем ту же страницу и смотрим, на месте ли места.
    Нужно, чтобы отличить: слот был и его заняли  ИЛИ  парсер ошибся."""
    try:
        html,status=fetch(result['url'])
        if status!=200: return None
        y=int(str(result.get('month_value','')).split('-')[0])
        slots,_=parse_slots(html,y)
        return {x['date']:x['count'] for x in slots}
    except Exception as e:
        log(f"REVERIFY ERROR: {e}"); return None

def alert_slots(result,state):
    global turbo_until
    now=time.time(); key=result['key']
    new_dates,changed,removed=smart_diff(state,result,commit=False)
    emoji,tier,sms_count=tier_of(result['calendar_name'])
    # ── ПРАВИЛА (одинаковые для всех, VIP просто шлёт больше сообщений) ──
    #  Новая дата        → СРОЧНО (sms_count: Student 2 / Standard 5 / VIP 12)
    #  Мест стало БОЛЬШЕ → СРОЧНО (тот же sms_count → VIP автоматически агрессивнее)
    #  Мест стало МЕНЬШЕ → тишина у всех
    #  Слот исчез        → одно сообщение
    increased={d:(o,n) for d,(o,n) in changed.items() if n>o}
    decreased={d:(o,n) for d,(o,n) in changed.items() if n<o}
    urgent = bool(new_dates) or bool(increased)
    if not (urgent or removed):
        # только уменьшение (или ничего) — молча зафиксировать
        if changed:
            smart_diff(state,result,commit=True)
            log(f'[{key}] MEST AZALDI (sessiz: {tier}) — bildirim yok')
        else:
            log(f'[{key}] NO DIFF — те же слоты, молчим')
        return
    smart_diff(state,result,commit=True)
    slots=result['slots']; lines=[]; day_links=result.get('day_links',{}) or {}
    def _with_link(d,txt):
        lk=day_links.get(d)
        return txt+(f"\n   🔗 {lk}" if lk else "")
    for d in sorted(new_dates): lines.append(_with_link(d,f"🆕 {fmt_date(d)} — {new_dates[d]} мест"))
    for d in sorted(increased):
        o,n=increased[d]; lines.append(_with_link(d,f"📈 {fmt_date(d)} — мест стало больше: {o} → {n}"))
    for d in sorted(removed): lines.append(f"❌ {fmt_date(d)} — было {removed[d]}, исчезло")
    if new_dates or increased:
        _pick=sorted(set(new_dates)|set(increased))[0]
        lines.append(f"👆 На странице нажми дату {fmt_date(_pick)} → откроется форма")
    # ── ПОВТОРНАЯ ПРОВЕРКА: реально ли место ещё на сайте ──
    confirm_note=''
    if urgent and CONFIRM_BEFORE_ALERT:
        again=reverify(result)
        if again is None:
            confirm_note='\n❓ Повторная проверка не удалась (сайт не ответил)'
        else:
            watch=set(new_dates)|set(increased)
            still={d:c for d,c in again.items() if d in watch and c>0}
            if still: confirm_note=f'\n✅ Подтверждено повторной проверкой ({len(still)} дн.)'
            else: confirm_note='\n⚠️ При повторной проверке мест уже НЕ видно — вероятно, заняли за секунды'
    
    if new_dates: header=f"🚨🚨🚨 {emoji} {tier} | НОВЫЕ СЛОТЫ 🚨🚨🚨"
    elif increased: header=f"📈🚨 {emoji} {tier} | БОЛЬШЕ МЕСТ 🚨"
    else: header=f"{emoji} {tier} | СЛОТЫ ИСЧЕЗЛИ"
    nearest=f"\n📍 Ближайшая дата: {fmt_date(slots[0]['date'])}" if slots else ''
    msg=(f"{header} [{BOT_NAME}]\n🏷 {result['calendar_name']}\n📅 {result['month_title']}{nearest}\nВсего дней с местами: {len(slots)}\n"+'\n'.join(lines[:20])+confirm_note+f"\n👉 {result['url']}")
    append_history({'time':datetime.now().isoformat(timespec='seconds'),'calendar':result['calendar_name'],'month':result['month_title'],'url':result['url'],'slots':slots,'new':new_dates,'changed':{d:list(v) for d,v in changed.items()},'removed':removed,'snapshot':result.get('snapshot','')})
    if urgent:
        if AUTO_OPEN_BROWSER_ON_SLOT:
            try: webbrowser.open(result['url'])
            except Exception as e: log(f'BROWSER OPEN ERROR: {e}')
        if ENABLE_TURBO_AFTER_SLOT: turbo_until=time.time()+TURBO_SECONDS_AFTER_SLOT
        repeats=sms_count          # Student 2 / Standard 5 / VIP 12
    else:
        repeats=1  # только исчезновение — одно сообщение
    for i in range(repeats):
        send_message(('🔥 СРОЧНО! ' if i else '')+msg,False)
        if i+1<repeats: time.sleep(FLOOD_ALERT_DELAY)
    if SEND_HTML_ON_SLOT and result.get('snapshot') and new_dates: send_document(result['snapshot'],'HTML snapshot найденного слота')
    last_alert_time_by_key[key]=now; last_change_alert_time_by_key[key]=now

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

def known_slots_summary(state,limit=10):
    lines=[]
    for key,slots in sorted(state.get('slot_map',{}).items()):
        for d,c in sorted(slots.items()):
            emoji,tier,_=tier_of(key)
            lines.append(f"{emoji} {key}: {fmt_date(d)} — {c}")
    return '\n'.join(lines[:limit]) if lines else 'Открытых слотов сейчас не видно.'

def send_hourly_status(stats,state=None):
    global last_status_time
    now=time.time()
    if now-last_status_time<STATUS_INTERVAL: return
    state=state or {}
    lc=state.get('last_change_time','')
    changes_line=f"🔔 Последнее изменение: {lc}" if lc else "Изменений нет"
    msg=(f"ℹ️ STATUS [{BOT_NAME}]\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n{changes_line}\n"
         f"📋 Известные слоты:\n{known_slots_summary(state)}\n"
         f"🔥 Со слотами: {stats.get('SLOTS_FOUND',0)}\n0️⃣ Дни есть, мест нет: {stats.get('ZERO_SLOTS',0)}\n⬜ Пустые месяцы: {stats.get('EMPTY_MONTH',0)}\n⚠️ Ошибки/unknown: {stats.get('ERROR',0)+stats.get('HTTP_ERROR',0)+stats.get('UNKNOWN',0)}\n🤖 Бот работает")
    if send_message(msg,True): last_status_time=now

def do_full_scan():
    """Немедленный обход всех календарей: что ОТКРЫТО, что подготовлено но ЗАКРЫТО.
    Отвечает на вопрос 'не пропускаем ли мы VIP'."""
    send_message(f"🔍 Полная проверка запущена [{BOT_NAME}]...", True)
    open_rows=[]; hidden_rows=[]; errors=0
    tasks=build_tasks()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for fut in as_completed({ex.submit(check_one,t):t for t in tasks}):
            try: r=fut.result()
            except Exception: errors+=1; continue
            if r['state'] in ('ERROR','HTTP_ERROR'): errors+=1; continue
            emoji,tier,_=tier_of(r['calendar_name'])
            for s in r.get('slots',[]):
                open_rows.append(f"{emoji} {r['calendar_name']} / {r['month_title']}: {fmt_date(s['date'])} — {s['count']} мест ✅ОТКРЫТ")
            for d,v in (r.get('hidden') or {}).items():
                hidden_rows.append(f"{emoji} {r['calendar_name']} / {r['month_title']}: {fmt_date(d)} — {v['count']} мест 🔒закрыт")
    parts=[f"🔍 РЕЗУЛЬТАТ ПРОВЕРКИ [{BOT_NAME}]", f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"]
    parts.append(f"\n✅ ОТКРЫТЫЕ (можно записаться): {len(open_rows)}")
    parts += (sorted(open_rows)[:25] or ["   — нет"])
    parts.append(f"\n🔒 ПОДГОТОВЛЕНЫ, НО ЗАКРЫТЫ: {len(hidden_rows)}")
    parts += (sorted(hidden_rows)[:25] or ["   — нет"])
    if errors: parts.append(f"\n⚠️ Ошибок при проверке: {errors}")
    send_message("\n".join(parts), False)

def command_text(): return 'Команды:\n/scan — проверить всё сейчас (открытые + закрытые)\n/status — статус\n/pause — пауза\n/resume — продолжить\n/months — месяцы проверки\n/history — последние найденные слоты\n/turbo — ускорить на 5 минут\n/help — команды'

def handle_command(text,state):
    global paused,turbo_until
    cmd=text.strip().split()[0].lower()
    if cmd=='/pause': paused=True; send_message('⏸ Бот поставлен на паузу.')
    elif cmd=='/resume': paused=False; send_message('▶️ Бот продолжает проверку.')
    elif cmd=='/months': send_message('📅 Проверяемые месяцы:\n'+'\n'.join([m[1] for m in months_to_check()]))
    elif cmd=='/history': send_message('📊 Последние слоты:\n'+last_history())
    elif cmd=='/turbo': turbo_until=time.time()+TURBO_SECONDS_AFTER_SLOT; send_message(f'🔥 TURBO включён на {TURBO_SECONDS_AFTER_SLOT} сек.')
    elif cmd=='/status':
        st=state.get('last_stats',{})
        send_message(f"ℹ️ STATUS NOW [{BOT_NAME}]\nПауза: {'да' if paused else 'нет'}\nTurbo: {'да' if time.time()<turbo_until else 'нет'}\nПоследний круг: {state.get('last_circle_time','-')}\nПоследнее изменение: {state.get('last_change_time','-') or '-'}\nПроверок: {sum(st.values())}\nСлоты: {st.get('SLOTS_FOUND',0)}\nБез мест: {st.get('ZERO_SLOTS',0)}\nПустые: {st.get('EMPTY_MONTH',0)}\nОшибки: {st.get('ERROR',0)+st.get('HTTP_ERROR',0)+st.get('UNKNOWN',0)}\n📋 Известные слоты:\n{known_slots_summary(state)}")
    elif cmd=='/scan':
        threading.Thread(target=do_full_scan, daemon=True).start()
    elif cmd=='/help': send_message(command_text())

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
    log(f'🚀 BOT START {BOT_NAME}'); send_message(f'✅ ULTRA режим: бот запущен ({BOT_NAME})\nFlood alert: {FLOOD_ALERT_COUNT} сообщений\n{command_text()}',False)
    state=load_state()
    if ENABLE_COMMANDS: threading.Thread(target=command_loop,args=(state,),daemon=True).start()
    while True:
        if paused: log('PAUSED'); time.sleep(5); continue
        tasks=build_tasks(); stats={}; log(f'TASKS: {len(tasks)} | MONTHS_AHEAD={MONTHS_AHEAD} | WORKERS={MAX_WORKERS}')
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            for fut in as_completed({ex.submit(check_one,t):t for t in tasks}):
                result=fut.result(); st=result['state']; stats[st]=stats.get(st,0)+1
                early_signal(result,state)
                if st=='SLOTS_FOUND': log(f"[{result['key']}] SLOTS: {result['slots']}"); alert_slots(result,state)
                elif st in ('ERROR','HTTP_ERROR'): log(f"[{result['key']}] {st}: {result.get('error','')}"); alert_error_once(result)
                elif st=='UNKNOWN': log(f"[{result['key']}] UNKNOWN PAGE, SNAP={result.get('snapshot','')}")
                else:
                    log(f"[{result['key']}] {st}")
                    check_slots_gone(result,state)
                time.sleep(random.uniform(0.05,0.25))
        state['last_stats']=stats; state['last_circle_time']=datetime.now().strftime('%d.%m.%Y %H:%M:%S'); save_state(state)
        send_heartbeat(stats); send_hourly_status(stats,state)
        if time.time()<turbo_until: sl=random.uniform(TURBO_SLEEP_MIN,TURBO_SLEEP_MAX); log(f'TURBO SLEEP: {round(sl,1)} sec')
        else: sl=random.uniform(NORMAL_SLEEP_MIN,NORMAL_SLEEP_MAX); log(f'SLEEP: {round(sl,1)} sec')
        time.sleep(sl)

if __name__=='__main__': main()
