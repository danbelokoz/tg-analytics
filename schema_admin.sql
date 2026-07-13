-- Аккаунты и мониторинг пайплайнов сбора. Выполнить один раз в Supabase → SQL Editor.
-- Таблицы читаются/пишутся только с service_role (через Vercel-функции), поэтому RLS
-- можно оставить включённым без политик — анонимному ключу доступа нет.

-- ── Пользователи ─────────────────────────────────────────────────────────────
create table if not exists app_users (
  id         uuid primary key default gen_random_uuid(),
  email      text unique not null,
  pass_hash  text not null,                     -- scrypt: "saltHex:hashHex" (см. api/_auth.js)
  role       text not null default 'user',      -- 'user' | 'admin'
  created_at timestamptz not null default now()
);

-- ── Прогоны пайплайнов (дешборд «последнее обновление / успех / ошибки») ──────
create table if not exists pipeline_runs (
  id          bigserial primary key,
  workflow    text not null,                    -- 'tg' | 'sites'
  ok          boolean not null default true,    -- прогон успешен (с учётом health-check)
  total       integer,                          -- собрано записей
  prev_total  integer,                          -- было в прошлый раз (для health-check)
  failed      integer not null default 0,       -- сколько под-источников упало
  error       text,                             -- текст ошибки/предупреждения (null = чисто)
  meta        jsonb,                            -- детали: {failed:[...], zeroed:[...]}
  finished_at timestamptz not null default now()
);
create index if not exists pipeline_runs_finished_idx on pipeline_runs (finished_at desc);
create index if not exists pipeline_runs_workflow_idx on pipeline_runs (workflow, finished_at desc);

-- ── Сид админ-аккаунта (пароль хранится только хешем) ─────────────────────────
-- Хеш для disaded@gmail.com посчитан scrypt'ом из api/_auth.js. Пароль в открытом
-- виде нигде не хранится; при желании смени его через вход → (позже) смену пароля.
insert into app_users (email, pass_hash, role)
values (
  'disaded@gmail.com',
  '8992235f78d1a229ac793b414f80a28f:20fc6b01976d650fa7b671bb32777e9159dc0a7037efc2f885bba150e561d23c17d2455d6a784c810723b4ad09702cbf7bd124afbe3d3258a9db0e17c17e3899',
  'admin'
)
on conflict (email) do update set role = 'admin';
