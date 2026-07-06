#!/usr/bin/env python3
"""
TG Analytics — экспорт данных из Supabase в статические JSON рядом со статикой.

Зачем: фронт (index.html / jobs.html) не должен ходить в *.supabase.co из браузера —
этот домен на AWS и режется DPI в РФ (см. PROJECT.md «Доступность в РФ без VPN»).
Данные не realtime (скрейпер обновляет их по расписанию), поэтому CI после сбора
запускает этот скрипт, кладёт JSON в data/ и коммитит — Vercel редеплоит, а браузер
грузит только наш домен.

Пишет:
  data/analytics_latest.json       — каталог каналов (index.html)
  data/subscriber_snapshots.json   — точки спарклайнов за 30 дней (index.html)
  data/job_feed.json               — лента вакансий (jobs.html)

ENV: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
     OUT_DIR — каталог вывода, дефолт data/
"""
import os
import sys
import json
import datetime as dt

import requests

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
OUT_DIR = os.environ.get("OUT_DIR", "data")

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}


def fetch_all(path, params, page=1000):
    """Читает таблицу/вью постранично (Supabase режет ответ лимитом)."""
    rows, off = [], 0
    while True:
        p = dict(params, limit=page, offset=off)
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{path}", headers=SB_HEADERS,
                         params=p, timeout=60)
        r.raise_for_status()
        chunk = r.json()
        rows += chunk
        if len(chunk) < page:
            return rows
        off += page


def write_json(name, rows):
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, name)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, separators=(",", ":"), default=str)
    print(f"  {out}: {len(rows)} строк")


def main():
    print(f"Экспорт из {SUPABASE_URL} → {OUT_DIR}/")

    # Каталог каналов — как в index.html (order subscribers desc nullslast).
    write_json("analytics_latest.json", fetch_all(
        "analytics_latest",
        {"select": "*", "order": "subscribers.desc.nullslast"},
    ))

    # Спарклайны — только последние 30 дней, по возрастанию даты.
    since = (dt.date.today() - dt.timedelta(days=30)).isoformat()
    write_json("subscriber_snapshots.json", fetch_all(
        "subscriber_snapshots",
        {"select": "username,snapshot_date,subscribers",
         "snapshot_date": f"gte.{since}",
         "order": "snapshot_date.asc"},
    ))

    # Лента вакансий — свежие сверху, первые 500 (как было на фронте).
    r = requests.get(f"{SUPABASE_URL}/rest/v1/job_feed", headers=SB_HEADERS,
                     params={"select": "*", "order": "posted_at.desc", "limit": 500},
                     timeout=60)
    r.raise_for_status()
    write_json("job_feed.json", r.json())

    print("Готово.")


if __name__ == "__main__":
    main()
