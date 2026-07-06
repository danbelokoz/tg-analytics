#!/usr/bin/env python3
"""
TG Analytics — сценарий 2: снимаем число подписчиков публичных каналов
со страницы https://t.me/<username> (HTTP, без аккаунта → банить нечего),
пишем дневные снапшоты в Supabase (analytics_channels + subscriber_snapshots).

Масштаб: тысячи каналов, 1 HTTP-запрос на канал, раз в сутки.

ENV (GitHub Secrets):
  SUPABASE_URL                — https://xxx.supabase.co
  SUPABASE_SERVICE_ROLE_KEY   — service role key (обходит RLS)
  SEED_FILE                   — (опц.) путь к файлу с @username по строке:
                                новые каналы засидятся в analytics_channels
  CONCURRENCY                 — (опц.) одновременных запросов, дефолт 8 (вежливо к t.me)
  REQ_DELAY                   — (опц.) пауза после запроса, сек, дефолт 0.15
"""
import os
import re
import sys
import json
import time
import asyncio
import datetime as dt

import aiohttp

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SEED_FILE    = os.environ.get("SEED_FILE", "").strip()
CONCURRENCY  = int(os.environ.get("CONCURRENCY", "8"))
REQ_DELAY    = float(os.environ.get("REQ_DELAY", "0.15"))
UA           = "Mozilla/5.0 (compatible; tg-analytics/1.0; +https://t.me)"

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# ── Парсинг страницы t.me/<username> ─────────────────────────────────────────

_RE_EXTRA = re.compile(r'tgme_page_extra">([^<]*)')
_RE_COUNT = re.compile(r'([\d\s  .,]+?)\s*(?:subscriber|member|подписчик|участник)', re.I)
_RE_OG    = lambda p: re.compile(rf'<meta property="og:{p}" content="([^"]*)"')
_RE_TITLE, _RE_IMAGE, _RE_DESC = _RE_OG("title"), _RE_OG("image"), _RE_OG("description")
# Пустой/несуществующий/приватный канал: t.me отдаёт страницу-заглушку без tgme_page_extra
_RE_NOT_FOUND = re.compile(r'tgme_page_additional">[^<]*(?:doesn.t exist|not found)', re.I)


def parse_page(html):
    """→ dict(subscribers,title,about,photo_url) или None, если это не публичный канал."""
    m = _RE_EXTRA.search(html)
    if not m:
        return None
    mc = _RE_COUNT.search(m.group(1))
    if not mc:
        return None  # extra есть, но без «subscribers» (например, «online» у бота)
    digits = re.sub(r"\D", "", mc.group(1))
    if not digits:
        return None
    subs = int(digits)

    def og(rx):
        g = rx.search(html)
        return g.group(1) if g else None

    return {
        "subscribers": subs,
        "title": og(_RE_TITLE),
        "about": og(_RE_DESC),
        "photo_url": og(_RE_IMAGE),
    }


# ── Supabase ─────────────────────────────────────────────────────────────────

def sb_get(table, params):
    import requests  # ленивый импорт: только для синхронных чтений сидов
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=SB_HEADERS,
                     params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def sb_active_usernames():
    rows, step, off = [], 1000, 0
    while True:
        chunk = sb_get("analytics_channels",
                       {"select": "username", "is_active": "eq.true",
                        "limit": step, "offset": off})
        rows += chunk
        if len(chunk) < step:
            break
        off += step
    return [r["username"] for r in rows]


def sb_upsert(table, rows, on_conflict):
    if not rows:
        return
    import requests
    h = dict(SB_HEADERS)
    h["Prefer"] = "resolution=merge-duplicates,return=minimal"
    # шлём батчами, чтобы не упереться в размер запроса на тысячах строк
    for i in range(0, len(rows), 500):
        batch = rows[i:i + 500]
        r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=h,
                          params={"on_conflict": on_conflict},
                          data=json.dumps(batch, default=str), timeout=60)
        if not r.ok:
            print(f"  ! supabase {table} {r.status_code}: {r.text[:300]}", file=sys.stderr)
        r.raise_for_status()


def seed_from_file(path):
    with open(path, encoding="utf-8") as f:
        names = [ln.strip().lstrip("@").split("/")[-1] for ln in f if ln.strip()
                 and not ln.startswith("#")]
    names = list(dict.fromkeys(names))
    if names:
        sb_upsert("analytics_channels",
                  [{"username": n} for n in names], "username")
        print(f"Засидили из {path}: {len(names)} каналов")
    return names


# ── Асинхронный обход ────────────────────────────────────────────────────────

async def fetch_channel(session, sem, username):
    url = f"https://t.me/{username}"
    async with sem:
        try:
            async with session.get(url, allow_redirects=True) as resp:
                if resp.status != 200:
                    return username, None, f"http {resp.status}"
                html = await resp.text()
        except Exception as e:  # noqa: BLE001
            return username, None, f"{type(e).__name__}"
        finally:
            if REQ_DELAY:
                await asyncio.sleep(REQ_DELAY)
    return username, parse_page(html), None


async def run(usernames):
    today = dt.datetime.utcnow().date().isoformat()
    now = dt.datetime.utcnow().isoformat()
    sem = asyncio.Semaphore(CONCURRENCY)
    timeout = aiohttp.ClientTimeout(total=30)
    channels, snapshots = [], []
    ok = skipped = 0

    async with aiohttp.ClientSession(timeout=timeout,
                                     headers={"User-Agent": UA}) as session:
        tasks = [fetch_channel(session, sem, u) for u in usernames]
        for i, coro in enumerate(asyncio.as_completed(tasks), 1):
            username, data, err = await coro
            if data is None:
                skipped += 1
                print(f"[{i}/{len(usernames)}] @{username}: skip ({err or 'not a channel'})",
                      file=sys.stderr)
                continue
            ok += 1
            channels.append({
                "username": username,
                "title": data["title"],
                "about": data["about"],
                "photo_url": data["photo_url"],
                "last_subscribers": data["subscribers"],
                "last_checked_at": now,
            })
            snapshots.append({
                "username": username,
                "snapshot_date": today,
                "captured_at": now,
                "subscribers": data["subscribers"],
            })
            if i % 100 == 0:
                print(f"[{i}/{len(usernames)}] ok={ok} skip={skipped}")

    sb_upsert("analytics_channels", channels, "username")
    sb_upsert("subscriber_snapshots", snapshots, "username,snapshot_date")
    print(f"Готово: спарсено {ok}, пропущено {skipped} из {len(usernames)}.")


def main():
    t0 = time.time()
    if SEED_FILE:
        seed_from_file(SEED_FILE)
    usernames = sb_active_usernames()
    if not usernames:
        print("Нет каналов. Задай SEED_FILE=... с @username по строке.")
        return
    print(f"Каналов к обработке: {len(usernames)} (concurrency={CONCURRENCY})")
    asyncio.run(run(usernames))
    print(f"Время: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
