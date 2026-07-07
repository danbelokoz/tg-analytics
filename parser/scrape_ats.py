#!/usr/bin/env python3
"""
TG Jobs — коннектор career-сайтов компаний (продукт 3: «Сайты работы»).

Тянет вакансии напрямую из ОФИЦИАЛЬНЫХ публичных job-board API их ATS
(Greenhouse / Lever / Ashby / SmartRecruiters / Workable) — это встраиваемые
API для витрин вакансий, а не парсинг чужого агрегатора. Список компаний и их
ATS-токены — в parser/companies_ats.json (см. как собирался: probe по слагам).

РФ-доступность: сбор идёт здесь, в CI. Браузер пользователя грузит только наш
статический data/company_jobs.json — на *.greenhouse.io/*.ashbyhq.com/... он не
ходит (см. PROJECT.md «Доступность в РФ без VPN»). Supabase не задействован:
career-вакансиям не нужен join с аналитикой Telegram-каналов.

Пишет: data/company_jobs.json — единый список карточек для витрины.

ENV:
  SEED     — путь к seed, дефолт parser/companies_ats.json
  OUT      — путь вывода, дефолт data/company_jobs.json
  CONCURRENCY — одновременных компаний, дефолт 12
  MAX_PER_COMPANY — ограничение вакансий с одной компании, дефолт 400
"""
import os
import re
import sys
import json
import html as _html
import datetime as dt
import concurrent.futures as cf
import urllib.request
import urllib.error

SEED = os.environ.get("SEED", os.path.join(os.path.dirname(__file__), "companies_ats.json"))
OUT = os.environ.get("OUT", "data/company_jobs.json")
CONCURRENCY = int(os.environ.get("CONCURRENCY", "12"))
MAX_PER_COMPANY = int(os.environ.get("MAX_PER_COMPANY", "400"))
UA = "Mozilla/5.0 (compatible; tg-jobs/1.0; +https://t.me)"

# ── Теги по тайтлу (роль/грейд/стек) ─────────────────────────────────────────
# Компактный вариант теггера из scrape_posts.py, заточенный под англ. тайтлы.
# Метки совпадают с лентой Telegram, чтобы фильтры на фронте были общими.
_CYR = re.compile(r"[а-яё]", re.I)


def _kw_rx(keywords):
    parts = []
    for k in keywords:
        esc = re.escape(k.strip())
        if _CYR.search(k):
            parts.append(r"(?<![а-яёa-z0-9])" + esc)
        else:
            parts.append(r"(?<![a-z0-9])" + esc + r"(?![a-z0-9])")
    return re.compile("|".join(parts), re.I)


def _compile(groups):
    return [(name, _kw_rx(kws)) for name, kws in groups]


ROLE = _compile([
    ("Frontend",   ["frontend", "front-end", "front end", "react", "vue", "angular"]),
    ("Backend",    ["backend", "back-end", "back end", "django", "node.js", "spring", "laravel"]),
    ("Fullstack",  ["fullstack", "full stack", "full-stack"]),
    ("Mobile",     ["mobile", "ios", "android", "flutter", "react native"]),
    ("DevOps",     ["devops", "sre", "kubernetes", "k8s", "infrastructure", "platform engineer"]),
    ("QA",         ["qa", "quality assurance", "test engineer", "sdet"]),
    ("Data/ML",    ["data scientist", "data analyst", "data engineer", "machine learning",
                    "ml engineer", "ai engineer", "deep learning", "research scientist"]),
    ("Аналитик",   ["analyst", "analytics"]),
    ("Design",     ["designer", "ui/ux", "ux", "ui ", "product design"]),
    ("Product",    ["product manager", "product owner", "head of product"]),
    ("Project",    ["project manager", "program manager", "delivery manager"]),
    ("Marketing",  ["marketing", "smm", "seo", "content", "growth"]),
    ("Sales",      ["sales", "account executive", "account manager", "business development"]),
    ("HR",         ["recruiter", "recruiting", "talent", "people ops", "hr "]),
    ("Management", ["head of", "lead", "director", "vp ", "chief", "manager", "cto", "ceo"]),
    ("Support",    ["support", "customer success", "customer experience"]),
])
STACK = _compile([
    ("Python",     ["python", "django", "fastapi"]),
    ("JS/TS",      ["javascript", "typescript", "node"]),
    ("Java",       ["java"]),
    ("PHP",        ["php", "laravel"]),
    ("Go",         ["golang", "go engineer", "go developer"]),
    (".NET/C#",    ["c#", ".net", "asp.net"]),
])
GRADE = _compile([
    ("Junior",     ["junior", "intern", "internship", "entry level", "graduate", "new grad"]),
    ("Middle",     ["middle"]),
    ("Senior",     ["senior", "sr.", "staff", "principal"]),
    ("Lead",       ["lead", "team lead", "tech lead"]),
])


def _hits(groups, text):
    return [name for name, rx in groups if rx.search(text)]


def tag_title(title):
    t = f" {title} "
    return list(dict.fromkeys(_hits(ROLE, t) + _hits(STACK, t) + _hits(GRADE, t)))


# ── work_format из строки локации / структурных флагов ───────────────────────
_RX_REMOTE = re.compile(r"\bremote\b|удал[её]н|дистанц|anywhere|work from home|wfh", re.I)
_RX_HYBRID = re.compile(r"\bhybrid\b|гибрид", re.I)
_RX_OFFICE = re.compile(r"\bon[- ]?site\b|\bin[- ]?office\b|офис", re.I)


def work_format(location, flag=None):
    """flag: 'remote'|'hybrid'|'onsite'|True|None — структурный признак из ATS."""
    if flag is True:
        return "Удалёнка"
    if isinstance(flag, str):
        f = flag.lower()
        if "remote" in f:
            return "Удалёнка"
        if "hybrid" in f:
            return "Гибрид"
        if "onsite" in f or "on_site" in f or "office" in f:
            return "Офис"
    loc = location or ""
    if _RX_HYBRID.search(loc):
        return "Гибрид"
    if _RX_REMOTE.search(loc):
        return "Удалёнка"
    if _RX_OFFICE.search(loc):
        return "Офис"
    return None


def _strip_html(s):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    return _html.unescape(re.sub(r"\s+", " ", s)).strip()


# ── HTTP ─────────────────────────────────────────────────────────────────────

def _get_json(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        if r.status != 200:
            raise urllib.error.HTTPError(url, r.status, "bad status", r.headers, None)
        return json.loads(r.read().decode("utf-8", "replace"))


def _iso(v):
    """Нормализует дату (ISO-строка или ms-таймстамп) в ISO-8601 или None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        try:
            return dt.datetime.utcfromtimestamp(v / 1000).replace(tzinfo=dt.timezone.utc).isoformat()
        except (ValueError, OSError):
            return None
    return str(v)


def _rec(company, slug, ats, ext_id, title, location, fmt, dept, url, posted, desc=""):
    return {
        "id": f"{ats}:{slug}:{ext_id}",
        "company": company,
        "company_slug": slug,
        "title": title,
        "location": location or None,
        "work_format": fmt,
        "department": dept or None,
        "apply_url": url,
        "posted_at": _iso(posted),
        "ats": ats,
        "tags": tag_title(title),
        "excerpt": _strip_html(desc)[:280] or None,
    }


# ── Парсеры по ATS ───────────────────────────────────────────────────────────

def fetch_greenhouse(c):
    d = _get_json(f"https://boards-api.greenhouse.io/v1/boards/{c['token']}/jobs?content=true")
    out = []
    for j in d.get("jobs", [])[:MAX_PER_COMPANY]:
        loc = (j.get("location") or {}).get("name")
        dept = None
        for m in j.get("metadata") or []:
            if m.get("name") in ("Career Site Categories", "Department") and m.get("value"):
                dept = m["value"]
                break
        out.append(_rec(c["name"], c["slug"], "greenhouse", j.get("id"),
                        j.get("title", "").strip(), loc, work_format(loc),
                        dept, j.get("absolute_url"), j.get("updated_at"),
                        j.get("content", "")))
    return out


def fetch_lever(c):
    d = _get_json(f"https://api.lever.co/v0/postings/{c['token']}?mode=json&limit={MAX_PER_COMPANY}")
    out = []
    for j in d[:MAX_PER_COMPANY]:
        cat = j.get("categories") or {}
        loc = cat.get("location")
        out.append(_rec(c["name"], c["slug"], "lever", j.get("id"),
                        (j.get("text") or "").strip(), loc,
                        work_format(loc, j.get("workplaceType")), cat.get("team"),
                        j.get("hostedUrl") or j.get("applyUrl"), j.get("createdAt"),
                        j.get("descriptionPlain", "")))
    return out


def fetch_ashby(c):
    d = _get_json(f"https://api.ashbyhq.com/posting-api/job-board/{c['token']}?includeCompensation=false")
    out = []
    for j in d.get("jobs", [])[:MAX_PER_COMPANY]:
        if j.get("isListed") is False:
            continue
        loc = j.get("location")
        flag = "remote" if j.get("isRemote") else j.get("workplaceType")
        out.append(_rec(c["name"], c["slug"], "ashby", j.get("id"),
                        (j.get("title") or "").strip(), loc, work_format(loc, flag),
                        j.get("department") or j.get("team"),
                        j.get("jobUrl") or j.get("applyUrl"), j.get("publishedAt"),
                        j.get("descriptionHtml", "")))
    return out


def fetch_smartrecruiters(c):
    out, off, step = [], 0, 100
    while len(out) < MAX_PER_COMPANY:
        d = _get_json(f"https://api.smartrecruiters.com/v1/companies/{c['token']}/postings"
                      f"?limit={step}&offset={off}")
        chunk = d.get("content", [])
        for j in chunk:
            lc = j.get("location") or {}
            loc = lc.get("fullLocation") or ", ".join(
                x for x in [lc.get("city"), lc.get("country", "").upper()] if x)
            flag = "remote" if lc.get("remote") else ("hybrid" if lc.get("hybrid") else "onsite")
            dept = (j.get("function") or {}).get("label") or (j.get("department") or {}).get("label")
            out.append(_rec(c["name"], c["slug"], "smartrecruiters", j.get("id"),
                            (j.get("name") or "").strip(), loc, work_format(loc, flag),
                            dept, f"https://jobs.smartrecruiters.com/{c['token']}/{j.get('id')}",
                            j.get("releasedDate")))
        off += step
        if len(chunk) < step:
            break
    return out[:MAX_PER_COMPANY]


_WD_REL = re.compile(r"(\d+)\s*\+?\s*day", re.I)


def _workday_date(s):
    """Workday отдаёт относительную дату («Posted 5 Days Ago») — переводим в
    приблизительный ISO, чтобы карточка сортировалась в общей ленте."""
    if not s:
        return None
    s = s.lower()
    now = dt.datetime.now(dt.timezone.utc)
    if "today" in s:
        return now.isoformat()
    if "yesterday" in s:
        return (now - dt.timedelta(days=1)).isoformat()
    m = _WD_REL.search(s)
    if m:
        return (now - dt.timedelta(days=int(m.group(1)))).isoformat()
    return None


def fetch_workday(c):
    base = f"https://{c['tenant']}.{c['dc']}.myworkdayjobs.com"
    cxs = f"{base}/wday/cxs/{c['tenant']}/{c['site']}/jobs"
    out, off = [], 0
    while len(out) < MAX_PER_COMPANY:
        body = json.dumps({"appliedFacets": {}, "limit": 20, "offset": off,
                           "searchText": ""}).encode()
        req = urllib.request.Request(cxs, data=body, headers={
            "User-Agent": UA, "Content-Type": "application/json", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        posts = d.get("jobPostings", [])
        for j in posts:
            path = j.get("externalPath", "")
            loc = j.get("locationsText")
            title = (j.get("title") or "").strip()
            ext = (j.get("bulletFields") or [path])[0]
            out.append(_rec(c["name"], c["slug"], "workday", ext, title, loc,
                            work_format(f"{title} {loc or ''}"), None,
                            f"{base}/en-US/{c['site']}{path}", _workday_date(j.get("postedOn"))))
        off += len(posts)
        if not posts or off >= d.get("total", 0):
            break
    return out[:MAX_PER_COMPANY]


def fetch_workable(c):
    d = _get_json(f"https://apply.workable.com/api/v1/widget/accounts/{c['token']}?details=true")
    out = []
    for j in d.get("jobs", [])[:MAX_PER_COMPANY]:
        loc = ", ".join(x for x in [j.get("city"), j.get("country")] if x) or j.get("location")
        out.append(_rec(c["name"], c["slug"], "workable", j.get("shortcode") or j.get("id"),
                        (j.get("title") or "").strip(), loc,
                        work_format(loc, "remote" if j.get("telecommuting") else None),
                        j.get("department"), j.get("url") or j.get("shortlink"),
                        j.get("published_on"), j.get("description", "")))
    return out


FETCH = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "smartrecruiters": fetch_smartrecruiters,
    "workable": fetch_workable,
    "workday": fetch_workday,
}


def scrape_company(c):
    fn = FETCH.get(c["ats"])
    if not fn:
        return c, [], f"no fetcher for {c['ats']}"
    try:
        return c, fn(c), None
    except Exception as e:  # noqa: BLE001
        return c, [], f"{type(e).__name__}: {e}"


def main():
    companies = json.load(open(SEED, encoding="utf-8"))
    print(f"Компаний в seed: {len(companies)} (concurrency={CONCURRENCY})")
    all_jobs, ok, fail = [], 0, 0
    with cf.ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        for i, (c, jobs, err) in enumerate(ex.map(scrape_company, companies), 1):
            if err:
                fail += 1
                print(f"[{i}/{len(companies)}] {c['name']}: {err}", file=sys.stderr)
                continue
            ok += 1
            all_jobs += jobs
            print(f"[{i}/{len(companies)}] {c['name']} ({c['ats']}): {len(jobs)}")

    # свежие сверху; вакансии без даты — в конец
    all_jobs.sort(key=lambda j: j.get("posted_at") or "", reverse=True)
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Готово: {ok} компаний ок, {fail} с ошибкой, {len(all_jobs)} вакансий → {OUT}")


if __name__ == "__main__":
    main()
