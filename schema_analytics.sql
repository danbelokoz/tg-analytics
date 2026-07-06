-- TG Analytics — сценарий 2: аналитика подписчиков по 1000+ каналам.
-- Данные берём HTTP-скрейпом публичной страницы t.me/<username> (без аккаунта),
-- поэтому ключ — username (внутренний Telegram-id при скрейпе недоступен).
-- Держим ОТДЕЛЬНО от тяжёлых таблиц вакансий (channels/posts) — это лёгкий поток.
--
-- Выполнить в Supabase SQL Editor один раз.

-- 1. Справочник каналов для аналитики
create table if not exists public.analytics_channels (
  username         text primary key,          -- @username без @
  title            text,
  about            text,
  photo_url        text,
  category         text,
  is_active        boolean not null default true,
  last_subscribers integer,                    -- денормализация: последнее значение для быстрого списка
  last_checked_at  timestamptz,
  added_at         timestamptz not null default now()
);

-- 2. Снимки подписчиков во времени — 1 в день
create table if not exists public.subscriber_snapshots (
  username      text not null references public.analytics_channels(username) on delete cascade,
  snapshot_date date not null default (now() at time zone 'utc')::date,
  captured_at   timestamptz not null default now(),
  subscribers   integer,
  primary key (username, snapshot_date)
);
create index if not exists idx_subsnap_user_date
  on public.subscriber_snapshots (username, snapshot_date desc);

-- 3. View для дашборда аналитики: последнее значение + рост за 1 и 7 дней
create or replace view public.analytics_latest as
select
  c.username, c.title, c.photo_url, c.category,
  latest.subscribers,
  latest.snapshot_date,
  (latest.subscribers - day_ago.subscribers)  as growth_1d,
  (latest.subscribers - week_ago.subscribers) as growth_7d,
  case when week_ago.subscribers > 0
       then round(100.0 * (latest.subscribers - week_ago.subscribers) / week_ago.subscribers, 2)
       else null end                          as growth_7d_pct
from public.analytics_channels c
left join lateral (
  select subscribers, snapshot_date from public.subscriber_snapshots
  where username = c.username order by snapshot_date desc limit 1
) latest on true
left join lateral (
  select subscribers from public.subscriber_snapshots
  where username = c.username and snapshot_date <= (now() - interval '1 day')::date
  order by snapshot_date desc limit 1
) day_ago on true
left join lateral (
  select subscribers from public.subscriber_snapshots
  where username = c.username and snapshot_date <= (now() - interval '7 days')::date
  order by snapshot_date desc limit 1
) week_ago on true
where c.is_active;

-- RLS: публичное чтение, запись только service_role (скрейпер)
alter table public.analytics_channels    enable row level security;
alter table public.subscriber_snapshots  enable row level security;

drop policy if exists "public read analytics_channels"   on public.analytics_channels;
drop policy if exists "public read subscriber_snapshots" on public.subscriber_snapshots;
create policy "public read analytics_channels"   on public.analytics_channels   for select using (true);
create policy "public read subscriber_snapshots" on public.subscriber_snapshots for select using (true);

grant select on public.analytics_latest to anon, authenticated;
