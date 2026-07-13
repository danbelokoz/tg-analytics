#!/usr/bin/env python3
"""Чинит логотипы: часть скачалась как HTML-заглушка (soft-404 по apple-touch-icon),
часть не скачалась. Перекачиваем все невалидные через DuckDuckGo (надёжный .ico),
конвертим в PNG (sips) и ПРОВЕРЯЕМ PNG-сигнатуру. Затем пересобираем манифест.
"""
import os, ssl, time, subprocess, urllib.request
from fetch_logos import DOMAINS, OUT

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
UA = {"User-Agent":"Mozilla/5.0 logo-bundler/1.0"}
CTX = ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE

def is_png(path):
    try:
        with open(path,"rb") as f: return f.read(8)==PNG_MAGIC
    except Exception: return False

def get(url, tries=4, timeout=20):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=UA),
                                        timeout=timeout, context=CTX) as r:
                d=r.read()
                if d and len(d)>200: return d
        except Exception: time.sleep(1.0*(i+1))
    return None

def ico_to_png(raw, dest):
    tmp=dest+".ico"
    with open(tmp,"wb") as f: f.write(raw)
    subprocess.run(["sips","-s","format","png",tmp,"--out",dest],
                   capture_output=True, text=True)
    os.remove(tmp)
    return is_png(dest)

fixed, still_bad = [], []
for slug, dom in sorted(DOMAINS.items()):
    dest=os.path.join(OUT, slug+".png")
    if is_png(dest):
        continue                      # уже валидный
    raw=get(f"https://icons.duckduckgo.com/ip3/{dom}.ico")
    if raw and ico_to_png(raw, dest):
        fixed.append(slug); print(f"  fixed {slug:24s} {dom}")
    else:
        if os.path.exists(dest): os.remove(dest)   # выкинуть HTML-мусор
        still_bad.append(slug); print(f"  BAD   {slug:24s} {dom}")

# пересобрать манифест из реально валидных PNG
valid=sorted(s for s in DOMAINS if is_png(os.path.join(OUT,s+".png")))
with open(os.path.join(OUT,"_manifest.txt"),"w") as f: f.write("\n".join(valid))
print(f"\nПочинено: {len(fixed)}; всё ещё без лого: {len(still_bad)} -> {still_bad}")
print(f"Валидных лого в манифесте: {len(valid)}")
