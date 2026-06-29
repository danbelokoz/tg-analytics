#!/usr/bin/env python3
"""
TG Analytics parser — собирает метрики публичных каналов через MTProto (Telethon)
и пишет снимки в Supabase. Запускается по cron в GitHub Actions.

ENV (GitHub Secrets):
  TG_API_ID, TG_API_HASH      — с https://my.telegram.org/apps
  TG_SESSION                  — StringSession (см. parser/gen_session.py)
  SUPABASE_URL                — https://xxx.supabase.co
  SUPABASE_SERVICE_ROLE_KEY   — service role key (обходит RLS)
  CHANNELS                    — (опц.) "durov,telegram" — засидить каналы при первом запуске
  POSTS_LIMIT                 — (опц.) сколько последних постов тянуть, дефолт 30
"""
import os
import sys
import json
import time
import datetime as dt

import requests
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.errors import FloodWaitError, ChannelPrivateError, UsernameNotOccupiedError

API_ID       = int(os.environ["TG_API_ID"])
API_HASH     = os.environ["TG_API_HASH"]
SESSION      = os.environ["TG_SESSION"]
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
POSTS_LIMIT  = int(os.environ.get("POSTS_LIMIT", "30"))
SEED         = [c.strip().lstrip("@") for c in os.environ.get("CHANNELS", "").split(",") if c.strip()]

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def sb_active_usernames():
    """Каналы, помеченные is_active в БД."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/channels",
        headers=SB_HEADERS,
        params={"select": "username", "is_active": "eq.true"},
        timeout=30,
    )
    r.raise_for_status()
    return [row["username"] for row in r.json()]


def sb_upsert(table, rows, on_conflict):
    if not rows:
        return
    h = dict(SB_HEADERS)
    h["Prefer"] = "resolution=merge-duplicates,return=minimal"
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=h,
        params={"on_conflict": on_conflict},
        data=json.dumps(rows, default=str),
        timeout=60,
    )
    if not r.ok:
        print(f"  ! supabase {table} {r.status_code}: {r.text[:300]}", file=sys.stderr)
    r.raise_for_status()


def reactions_count(msg):
    if not getattr(msg, "reactions", None) or not msg.reactions.results:
        return 0
    return sum(rr.count for rr in msg.reactions.results)


def parse_channel(client, username):
    entity = client.get_entity(username)
    full = client(GetFullChannelRequest(entity)).full_chat

    channel = {
        "id": entity.id,
        "username": entity.username or username,
        "title": entity.title,
        "about": full.about,
        "is_active": True,
    }
    snapshot = {
        "channel_id": entity.id,
        "snapshot_date": dt.datetime.utcnow().date().isoformat(),
        "captured_at": dt.datetime.utcnow().isoformat(),
        "subscribers": full.participants_count,
    }

    posts = []
    for msg in client.iter_messages(entity, limit=POSTS_LIMIT):
        if msg.id is None:
            continue
        posts.append({
            "channel_id": entity.id,
            "message_id": msg.id,
            "posted_at": msg.date.isoformat() if msg.date else None,
            "text": (msg.message or "")[:2000],
            "views": msg.views or 0,
            "forwards": msg.forwards or 0,
            "replies": (msg.replies.replies if msg.replies else 0),
            "reactions": reactions_count(msg),
            "updated_at": dt.datetime.utcnow().isoformat(),
        })

    return channel, snapshot, posts


def main():
    usernames = list(dict.fromkeys(SEED + sb_active_usernames()))  # uniq, seed первым
    if not usernames:
        print("Нет каналов. Задай CHANNELS=durov,telegram или добавь строки в таблицу channels.")
        return

    print(f"Каналов к обработке: {len(usernames)}")
    with TelegramClient(StringSession(SESSION), API_ID, API_HASH) as client:
        for i, uname in enumerate(usernames, 1):
            try:
                channel, snapshot, posts = parse_channel(client, uname)
                sb_upsert("channels", [channel], "id")
                sb_upsert("channel_snapshots", [snapshot], "channel_id,snapshot_date")
                sb_upsert("posts", posts, "channel_id,message_id")
                print(f"[{i}/{len(usernames)}] @{uname}: subs={snapshot['subscribers']}, posts={len(posts)}")
            except FloodWaitError as e:
                print(f"[{i}/{len(usernames)}] @{uname}: FloodWait {e.seconds}s — жду", file=sys.stderr)
                time.sleep(e.seconds + 1)
            except (ChannelPrivateError, UsernameNotOccupiedError, ValueError) as e:
                print(f"[{i}/{len(usernames)}] @{uname}: пропуск ({type(e).__name__})", file=sys.stderr)
            except Exception as e:  # noqa: BLE001 — не валим весь прогон из-за одного канала
                print(f"[{i}/{len(usernames)}] @{uname}: ошибка {type(e).__name__}: {e}", file=sys.stderr)
            time.sleep(2.5)  # gentle: не долбим Telegram (см. урок batching > concurrency)

    print("Готово.")


if __name__ == "__main__":
    main()
