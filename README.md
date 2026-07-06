# TG Analytics

Два продукта поверх Telegram-каналов о работе, оба питаются **HTTP-скрейпом публичных
страниц t.me — без Telegram-аккаунта** (банить нечего, масштабируется на тысячи каналов):

- **Аналитика подписчиков** (`index.html`, `/`) — рост аудитории каналов день ко дню.
- **Лента вакансий** (`jobs.html`, `/jobs`) — последние посты с авто-тегами (роль, формат,
  грейд, стек, з/п).

Скрейперы крутятся в GitHub Actions по cron, пишут в Supabase; статичный фронт на Vercel
читает данные напрямую через anon-ключ.

```
parser/scrape_subscribers.py     — подписчики со страницы t.me/<user>  (аналитика)
parser/scrape_posts.py           — посты со страницы t.me/s/<user> + авто-теги (лента)
parser/analytics_seed.txt        — список каналов (@username по строке)
parser/requirements_analytics.txt — зависимости скрейперов (aiohttp)
.github/workflows/analyze.yml    — подписчики: ежедневно + при пуше
.github/workflows/jobs.yml       — посты: каждые 3 часа + при пуше
schema_analytics.sql             — таблицы аналитики (analytics_channels, subscriber_snapshots)
schema_jobs.sql                  — таблицы ленты (job_posts, job_feed)
index.html / jobs.html           — фронт (читают Supabase через anon key)
vercel.json                      — статический хостинг
```

## Как это работает

- **Подписчики:** `t.me/<username>` (обычная страница) отдаёт точное число подписчиков в
  блоке `tgme_page_extra`. Скрейпер снимает снапшот раз в сутки → `subscriber_snapshots`,
  view `analytics_latest` считает рост за 1 и 7 дней.
- **Посты:** `t.me/s/<username>` (веб-превью ленты) отдаёт ~20 последних постов. Скрейпер
  парсит текст/дату/просмотры, проставляет теги регэкспами по тексту и флаг `is_vacancy`,
  пишет в `job_posts`; view `job_feed` отдаёт фронту только вакансии.
- Всё пишется через `upsert` (`on_conflict` + merge) — повторный прогон обновляет строки,
  а не плодит дубли (поэтому перетегирование постов работает «на месте»).

## Настройка

### 1. Supabase
1. Создай проект на supabase.com.
2. SQL Editor → выполни `schema_analytics.sql`, затем `schema_jobs.sql`.
3. Settings → API → возьми `Project URL`, `anon key`, `service_role key`.

### 2. GitHub Secrets
Repo → Settings → Secrets and variables → Actions → добавь:
`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.

### 3. Каналы и первый прогон
1. Впиши `@username` (по строке) в `parser/analytics_seed.txt`, закоммить.
2. Actions → *Analytics — subscriber snapshots* → Run workflow (или просто push в `main` —
   оба воркфлоу триггерятся на изменения скрейперов/сида). Это засеет каналы и снимет
   первые снапшоты. Лента наполнится ближайшим прогоном *Jobs — vacancy feed*.

### 4. Vercel
1. New Project → импортируй репо.
2. В `index.html` / `jobs.html` подставь свои `SUPABASE_URL` и `SUPABASE_ANON_KEY`.
3. Deploy.

## Заметки
- Аккаунт Telegram не нужен — только публичные страницы t.me. Никакого риска бана.
- Скрейперы вежливы к t.me: асинхронно, семафор на `CONCURRENCY` (дефолт 8) + пауза
  `REQ_DELAY` после запроса. На тысячах каналов держи concurrency умеренным.
- Точность подписчиков: страница `t.me/<user>` даёт точное число; `t.me/s/` округляет —
  поэтому для аналитики берём именно `t.me/<user>`.
- Теги ленты — эвристика по ключевым словам (границы слов + отдельная обработка дайджестов).
  Слово «аналитик»/«аналитика» неразличимо на уровне ключей — это предел без NLP.
- Легаси: `schema.sql` (таблицы `channels`/`posts`/`watchlist` от старого MTProto-парсера)
  больше не наполняется; оставлен как история модели. Кнопка «Добавить канал» на фронте
  всё ещё пишет в `watchlist` (не в аналитику) — на очереди перепрошивка.
