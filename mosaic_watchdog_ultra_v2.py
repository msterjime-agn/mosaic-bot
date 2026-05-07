import subprocess, time
from pathlib import Path
from datetime import datetime
BOT_FILE='mosaic_ultra_v2.py'
LOG_FILE=Path('./mosaic_bot_data/watchdog_ultra.log')
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
def log(t):
    line=f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {t}"
    print(line, flush=True)
    LOG_FILE.open('a', encoding='utf-8').write(line+'\n')
while True:
    log('STARTING BOT')
    p=subprocess.Popen(['py', BOT_FILE])
    code=p.wait()
    log(f'BOT EXITED WITH CODE {code}. RESTART IN 10 SEC')
    time.sleep(10)
