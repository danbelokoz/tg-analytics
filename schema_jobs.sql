-- TG Analytics — лента вакансий (продукт 1).
-- Посты тянем со страницы t.me/s/<username> (HTTP, без аккаунта).
-- Теги проставляет скрейпер по тексту (роль, формат, грейд, стек, з/п).
--
-- Выполнить в Supabase SQL Editor один раз. Зависит от analytics_channels (schema_analytics.sql).

create table if not exists public.job_posts (
  username    text   not null references public.analytics_channels(username) on delete cascade,
  message_id  bigint not null,
  posted_at   timestamptz,
  text        text,
  link        text,
  views       integer,
  tags        text[] not null default '{}',
  is_vacancy  boolean not null default false,   -- похоже ли на вакансию (есть роль/маркеры найма)
  updated_at  timestamptz not null default now(),
  primary key (username, message_id)
);
create index if not exists idx_jobposts_posted on public.job_posts (posted_at desc);
create index if not exists idx_jobposts_tags   on public.job_posts using gin (tags);

-- Лента для фронта: только вакансии, свежие сверху, с названием/аватаром канала
create or replace view public.job_feed as
select
  p.username, p.message_id, p.posted_at, p.text, p.link, p.views, p.tags,
  c.title as channel_title, c.photo_url as channel_photo
from public.job_posts p
join public.analytics_channels c on c.username = p.username
where p.is_vacancy
order by p.posted_at desc nulls last;

-- RLS: публичное чтение, запись только service_role (скрейпер)
alter table public.job_posts enable row level security;
drop policy if exists "public read job_posts" on public.job_posts;
create policy "public read job_posts" on public.job_posts for select using (true);

grant select on public.job_feed to anon, authenticated;
