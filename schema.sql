-- TG Analytics — Supabase schema
-- Выполнить один раз в Supabase SQL Editor (SQL Editor → New query → Run).
-- Данные публичные => anon только читает; пишет только парсер (service_role, обходит RLS).
--
-- ⚠️ Если в проекте остались объекты от прошлых запусков и ловишь
--    "column ... does not exist" — раскомментируй блок чистки ниже (СОТРЁТ данные):
-- drop view  if exists public.channel_latest;
-- drop table if exists public.posts             cascade;
-- drop table if exists public.channel_snapshots cascade;
-- drop table if exists public.channels          cascade;

-- 1. Справочник отслеживаемых каналов
create table if not exists public.channels (
  id          bigint primary key,          -- Telegram channel id
  username    text unique not null,        -- @username без @
  title       text,
  about       text,
  photo_url   text,
  category    text,
  is_active   boolean not null default true,
  added_at    timestamptz not null default now()
);

-- 2. Снимки метрик канала во времени (рост подписчиков) — 1 в день
create table if not exists public.channel_snapshots (
  id            bigserial primary key,
  channel_id    bigint not null references public.channels(id) on delete cascade,
  snapshot_date date   not null default (now() at time zone 'utc')::date,
  captured_at   timestamptz not null default now(),
  subscribers   integer,
  unique (channel_id, snapshot_date)
);
create index if not exists idx_snap_channel_date
  on public.channel_snapshots (channel_id, snapshot_date desc);

-- 3. Посты (engagement; upsert по channel_id+message_id обновляет растущие метрики)
create table if not exists public.posts (
  channel_id  bigint not null references public.channels(id) on delete cascade,
  message_id  bigint not null,
  posted_at   timestamptz,
  text        text,
  views       integer default 0,
  forwards    integer default 0,
  replies     integer default 0,
  reactions   integer default 0,
  updated_at  timestamptz not null default now(),
  primary key (channel_id, message_id)
);
create index if not exists idx_posts_channel_date
  on public.posts (channel_id, posted_at desc);

-- View для дашборда: последний снимок + рост за 7 дней + средний охват + ER
create or replace view public.channel_latest as
select
  c.id, c.username, c.title, c.photo_url, c.category,
  latest.subscribers,
  latest.snapshot_date,
  week_ago.subscribers                        as subscribers_7d_ago,
  (latest.subscribers - week_ago.subscribers) as growth_7d,
  eng.avg_views,
  case when latest.subscribers > 0
       then round(100.0 * eng.avg_views / latest.subscribers, 2)
       else null end                          as err_pct
from public.channels c
left join lateral (
  select subscribers, snapshot_date from public.channel_snapshots
  where channel_id = c.id order by snapshot_date desc limit 1
) latest on true
left join lateral (
  select subscribers from public.channel_snapshots
  where channel_id = c.id and snapshot_date <= (now() - interval '7 days')::date
  order by snapshot_date desc limit 1
) week_ago on true
left join lateral (
  select avg(views)::int as avg_views from (
    select views from public.posts where channel_id = c.id
    order by posted_at desc limit 20
  ) p
) eng on true
where c.is_active;

-- RLS: публичное чтение, запись только service_role (парсер)
alter table public.channels          enable row level security;
alter table public.channel_snapshots enable row level security;
alter table public.posts             enable row level security;

drop policy if exists "public read channels"  on public.channels;
drop policy if exists "public read snapshots" on public.channel_snapshots;
drop policy if exists "public read posts"     on public.posts;
create policy "public read channels"  on public.channels          for select using (true);
create policy "public read snapshots" on public.channel_snapshots for select using (true);
create policy "public read posts"     on public.posts             for select using (true);

-- Доступ для PostgREST: чтение view роли anon/authenticated (чтобы фронт не словил 401)
grant select on public.channel_latest to anon, authenticated;
