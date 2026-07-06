#!/usr/bin/env python3
"""
TG Analytics — лента вакансий (продукт 1): тянем последние посты каналов
со страницы https://t.me/s/<username> (HTTP, без аккаунта), проставляем теги
по тексту (роль/формат/грейд/стек/з-п) и пишем в Supabase (job_posts).

ENV:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
  CONCURRENCY  — одновременных запросов, дефолт 8
  REQ_DELAY    — пауза после запроса, сек, дефолт 0.15
"""
import os
import re
import sys
import json
import html as _html
import asyncio
import datetime as dt

import aiohttp

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
CONCURRENCY  = int(os.environ.get("CONCURRENCY", "8"))
REQ_DELAY    = float(os.environ.get("REQ_DELAY", "0.15"))
UA           = "Mozilla/5.0 (compatible; tg-analytics/1.0; +https://t.me)"

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# ── Теги: (тег, [ключевые слова в нижнем регистре]) ──────────────────────────
# Порядок = порядок вывода чипов. Совпадение по подстроке в тексте поста.
ROLE = [
    ("Frontend",   ["frontend", "фронтенд", "фронт", "react", "vue", "angular"]),
    ("Backend",    ["backend", "бэкенд", "бекенд", "бэк", "django", "node.js", "nodejs", "spring", "laravel"]),
    ("Fullstack",  ["fullstack", "full stack", "фулстек", "фулл-стек"]),
    ("Mobile",     ["mobile", " ios", "android", "flutter", "react native", "мобильн"]),
    ("DevOps",     ["devops", " sre", "kubernetes", "k8s", "ci/cd", "инфраструктур"]),
    ("QA",         [" qa", "qa-", "тестировщик", "тестирование", "автотест", "quality assurance"]),
    ("Data/ML",    ["data scientist", "data analyst", "data engineer", "аналитик данных",
                    " ml", "machine learning", "машинн", " bi ", "big data"]),
    ("Аналитик",   ["аналитик", "analyst", "системный аналитик", "бизнес-аналитик"]),
    ("Design",     ["дизайн", "designer", "ui/ux", "ux", " ui ", "продуктовый дизайн"]),
    ("Product",    ["продакт", "product manager", "продуктовый менеджер", "product owner"]),
    ("Project",    ["проджект", "project manager", "проектный менеджер", "delivery manager"]),
    ("Marketing",  ["маркетолог", "маркетинг", "marketing", "smm", " seo", "таргетолог", "контент-менеджер"]),
    ("Sales",      ["продаж", "sales", "менеджер по продажам", "account manager"]),
    ("HR",         [" hr ", "hr-", "рекрутер", "recruiter", "по персоналу"]),
    ("Management",  ["руководитель", "head of", "teamlead", "team lead", "тимлид", "cto", "директор"]),
    ("Support",    ["поддержк", "support", "техподдержк"]),
]
STACK = [
    ("Python",     ["python", "питон", "django", "fastapi"]),
    ("JS/TS",      ["javascript", " js ", "typescript", " ts ", "react", "node"]),
    ("Java",       [" java", "джава"]),
    ("PHP",        [" php", "laravel"]),
    ("Go",         ["golang", " go ", " go-"]),
    (".NET/C#",    ["c#", ".net", "asp.net"]),
    ("1C",         ["1с", "1c"]),
]
FORMAT = [
    ("Удалёнка",   ["удален", "удалён", "remote", "дистанционн", "из дома"]),
    ("Гибрид",     ["гибрид", "hybrid"]),
    ("Офис",       ["в офис", "офис,", "on-site", "on site", "на месте"]),
    ("Релокация",  ["релокац", "relocation", "релокейт", "переезд", "relocate"]),
]
GRADE = [
    ("Junior",     ["junior", "джун", "начинающ", "без опыта", "intern", "стажёр", "стажер"]),
    ("Middle",     ["middle", "миддл", "мидл"]),
    ("Senior",     ["senior", "сеньор", "синьор", "сениор"]),
    ("Lead",       [" lead", "тимлид", "team lead", "ведущий разработчик"]),
]
EMPLOY = [
    ("Стажировка", ["стажировк", "интернатур", "internship"]),
    ("Фриланс",    ["фриланс", "freelance", "проектн", "подработк", "разов"]),
    ("Part-time",  ["part-time", "part time", "частичн", "парт-тайм", "неполн"]),
]
_SALARY = re.compile(r"(\$\s?\d|\d[\d\s]*\s?(?:000|k\b|к\b|тыс)|₽|руб|€\s?\d|оклад|зарплат|от\s+\d|salary)", re.I)
# Маркеры того, что пост — вакансия (а не дайджест/реклама/новость)
_VAC = re.compile(r"(ваканс|ищем|требуется|в команду|hiring|we are looking|открыта позиц|нужен|нужна|"
                  r"обязанност|требовани|мы предлагаем|условия|з/п|з\\п|зарплат|оклад|remote|удален)", re.I)


def tag_post(text):
    t = " " + text.lower() + " "
    tags = []
    for group in (ROLE, STACK, FORMAT, GRADE, EMPLOY):
        for tag, kws in group:
            if any(k in t for k in kws):
                tags.append(tag)
    if _SALARY.search(text):
        tags.append("З/п указана")
    # дедуп с сохранением порядка
    tags = list(dict.fromkeys(tags))
    has_role = any(tag in {r[0] for r in ROLE} for tag in tags)
    is_vacancy = has_role or bool(_VAC.search(text))
    return tags, is_vacancy


# ── Парсинг t.me/s/<username> ────────────────────────────────────────────────

def _text_of(chunk):
    m = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', chunk, re.S)
    if not m:
        return ""
    raw = re.sub(r'<br\s*/?>', '\n', m.group(1))
    raw = re.sub(r'</?(?:a|b|i|s|u|strong|em|code|pre|span|tg-emoji|blockquote)[^>]*>', '', raw)
    raw = re.sub(r'<[^>]+>', '', raw)
    return _html.unescape(raw).strip()


def _views_to_int(s):
    s = s.strip().replace(",", ".").lower()
    mult = 1
    if s.endswith("k"): mult, s = 1000, s[:-1]
    elif s.endswith("m"): mult, s = 1_000_000, s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        return None


def parse_posts(html, username):
    posts = []
    chunks = html.split('tgme_widget_message_wrap')
    for ch in chunks:
        mp = re.search(r'data-post="[^"/]+/(\d+)"', ch)
        if not mp:
            continue
        text = _text_of(ch)
        if not text:
            continue  # медиа без подписи — пропускаем
        mid = int(mp.group(1))
        md = re.search(r'datetime="([^"]+)"', ch)
        mv = re.search(r'tgme_widget_message_views">([^<]+)<', ch)
        tags, is_vac = tag_post(text)
        posts.append({
            "username": username,
            "message_id": mid,
            "posted_at": md.group(1) if md else None,
            "text": text[:4000],
            "link": f"https://t.me/{username}/{mid}",
            "views": _views_to_int(mv.group(1)) if mv else None,
            "tags": tags,
            "is_vacancy": is_vac,
            "updated_at": dt.datetime.utcnow().isoformat(),
        })
    return posts


# ── Supabase ─────────────────────────────────────────────────────────────────

def sb_active_usernames():
    import requests
    rows, step, off = [], 1000, 0
    while True:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/analytics_channels", headers=SB_HEADERS,
                         params={"select": "username", "is_active": "eq.true",
                                 "limit": step, "offset": off}, timeout=30)
        r.raise_for_status()
        chunk = r.json()
        rows += chunk
        if len(chunk) < step:
            break
        off += step
    return [r["username"] for r in rows]


def sb_upsert(rows):
    if not rows:
        return
    import requests
    h = dict(SB_HEADERS)
    h["Prefer"] = "resolution=merge-duplicates,return=minimal"
    for i in range(0, len(rows), 500):
        batch = rows[i:i + 500]
        r = requests.post(f"{SUPABASE_URL}/rest/v1/job_posts", headers=h,
                          params={"on_conflict": "username,message_id"},
                          data=json.dumps(batch, default=str), timeout=60)
        if not r.ok:
            print(f"  ! supabase job_posts {r.status_code}: {r.text[:300]}", file=sys.stderr)
        r.raise_for_status()


# ── Асинхронный обход ────────────────────────────────────────────────────────

async def fetch_channel(session, sem, username):
    url = f"https://t.me/s/{username}"
    async with sem:
        try:
            async with session.get(url, allow_redirects=True) as resp:
                if resp.status != 200:
                    return username, [], f"http {resp.status}"
                html = await resp.text()
        except Exception as e:  # noqa: BLE001
            return username, [], type(e).__name__
        finally:
            if REQ_DELAY:
                await asyncio.sleep(REQ_DELAY)
    return username, parse_posts(html, username), None


async def run(usernames):
    sem = asyncio.Semaphore(CONCURRENCY)
    timeout = aiohttp.ClientTimeout(total=30)
    all_posts, vac = [], 0
    async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": UA}) as session:
        tasks = [fetch_channel(session, sem, u) for u in usernames]
        for i, coro in enumerate(asyncio.as_completed(tasks), 1):
            username, posts, err = await coro
            if err:
                print(f"[{i}/{len(usernames)}] @{username}: {err}", file=sys.stderr)
                continue
            v = sum(1 for p in posts if p["is_vacancy"])
            vac += v
            all_posts += posts
            print(f"[{i}/{len(usernames)}] @{username}: постов {len(posts)}, вакансий {v}")
    sb_upsert(all_posts)
    print(f"Готово: {len(all_posts)} постов, из них вакансий {vac}.")


def main():
    usernames = sb_active_usernames()
    if not usernames:
        print("Нет каналов в analytics_channels.")
        return
    print(f"Каналов к обработке: {len(usernames)} (concurrency={CONCURRENCY})")
    asyncio.run(run(usernames))


if __name__ == "__main__":
    main()

# re-run after schema applied
