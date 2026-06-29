# TG Analytics

Аналитика публичных Telegram-каналов: парсер собирает подписчиков/охваты/реакции
через MTProto (Telethon) по cron в GitHub Actions, пишет в Supabase, статичный
дашборд на Vercel читает данные напрямую.

```
parser/parse_channels.py   — парсер (Telethon → Supabase REST)
parser/gen_session.py      — разовая генерация TG_SESSION
.github/workflows/parse.yml — cron каждые 6 часов
schema.sql                  — таблицы + view + RLS (выполнить в Supabase)
index.html                  — дашборд (читает Supabase напрямую через anon key)
vercel.json                 — статический хостинг
```

## Архитектура и бесплатные лимиты
- **GitHub** — новый репо (тот же аккаунт). Публичный → безлимитные Actions-минуты.
- **Supabase** — НОВЫЙ проект (free даёт до 2; это второй). Парсер пишет ежедневно
  → проект не уснёт от неактивности.
- **Vercel** — новый проект (тот же аккаунт). Тут чистая статика, serverless-функций нет
  → лимит 12 функций не грозит.
- **Telegram** — ⚠️ ОТДЕЛЬНЫЙ (бёрнер) аккаунт под парсер, не личный (риск бана).

## Настройка (по шагам)

### 1. Supabase
1. Создай новый проект на supabase.com.
2. SQL Editor → выполни `schema.sql`.
3. Settings → API → возьми `Project URL`, `anon key`, `service_role key`.

### 2. Telegram
1. Заведи отдельный аккаунт (отдельный номер).
2. https://my.telegram.org/apps → создай приложение → получи `api_id` и `api_hash`.
3. Сгенерь сессию локально:
   ```bash
   cd parser && pip install -r requirements.txt
   TG_API_ID=... TG_API_HASH=... python gen_session.py
   ```
   Введи номер дедик-аккаунта + код. Скопируй строку `TG_SESSION`.

### 3. GitHub
Repo → Settings → Secrets and variables → Actions → добавь:
`TG_API_ID`, `TG_API_HASH`, `TG_SESSION`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.
Запусти первый прогон вручную: Actions → *Parse Telegram channels* → Run workflow,
в поле channels впиши, напр., `durov,telegram`.

### 4. Vercel
1. New Project → импортируй репо (тот же аккаунт).
2. В `index.html` подставь `SUPABASE_URL` и `SUPABASE_ANON_KEY`.
3. Deploy.

## Заметки
- `views`/`forwards`/`reactions` со временем растут — upsert по `(channel_id, message_id)`
  обновляет их при каждом проходе.
- Подписчики — снимок раз в день (`channel_snapshots`), отсюда «Рост 7д» во view.
- Парсер бережёт Telegram: пауза 2.5 c между каналами + обработка `FloodWait`.
  Не гони слишком часто/много за раз — словишь временный бан.
- Bot API НЕ подходит для чужих каналов (нужны права админа) — поэтому MTProto.
- Если my.telegram.org не даёт создать своё приложение (ERROR / `[object Object]` —
  частый гео/VPN-баг), на старте годится публичная пара `api_id=2040` /
  `api_hash=b18441a1ff607e10a989891a5462e627` (Telegram Desktop). Позже заменишь на свою —
  это лишь «ID приложения», на доступ к аккаунту не влияет.
- Генерацию сессии (`gen_session.py`) в стране с блокировкой Telegram делай **под VPN** —
  тогда прокси в коде не нужен. Парсеру на GitHub Actions VPN не нужен (раннеры за границей).
