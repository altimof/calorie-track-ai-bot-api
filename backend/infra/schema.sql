-- Database schema for Neon PostgreSQL.
-- Mirrors the live production schema (regenerated from pg_dump --schema-only on 2026-10-11).
-- Idempotent for a fresh database or one already at this schema. It does NOT upgrade an
-- older database (e.g. one built from a previous version of this file): `create table if not
-- exists` skips existing tables, so later statements that use new columns will fail.
-- There is no migration tool; apply schema changes to Neon directly and keep this file in sync.

create extension if not exists pgcrypto;

create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  telegram_id bigint unique,
  handle text,
  locale text,
  created_at timestamptz default now()
);

create table if not exists photos (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id),
  tigris_key text not null,
  status text not null default 'uploaded',
  meta jsonb default '{}'::jsonb,
  meal_id uuid, -- FK to meals added below (meals is created later)
  media_group_id varchar(255),
  display_order integer default 0 check (display_order >= 0 and display_order <= 4),
  created_at timestamptz default now()
);

create table if not exists estimates (
  id uuid primary key default gen_random_uuid(),
  photo_id uuid references photos(id),
  kcal_mean numeric,
  kcal_min numeric,
  kcal_max numeric,
  items jsonb,
  confidence numeric,
  status text default 'done',
  macronutrients jsonb,
  photo_count integer default 1,
  photo_ids text[],
  created_at timestamptz default now()
);

create table if not exists meals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id),
  meal_date date not null,
  meal_type text not null,
  kcal_total numeric not null,
  source text not null,
  estimate_id uuid constraint fk_meals_estimate references estimates(id),
  description text,
  protein_grams numeric(6,2) check (protein_grams >= 0),
  carbs_grams numeric(6,2) check (carbs_grams >= 0),
  fats_grams numeric(6,2) check (fats_grams >= 0),
  confidence_score numeric,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'photos_meal_id_fkey') then
    alter table photos add constraint photos_meal_id_fkey foreign key (meal_id) references meals(id);
  end if;
end $$;

create table if not exists goals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id),
  daily_kcal_target integer not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- user_id is the Telegram user ID as text, not a users.id FK
create table if not exists feedback_submissions (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  message_type text not null check (message_type in ('feedback', 'bug', 'question', 'support')),
  message_content text not null check (char_length(message_content) > 0 and char_length(message_content) <= 5000),
  user_context jsonb,
  status text not null default 'new' check (status in ('new', 'reviewed', 'resolved')),
  admin_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- user_id is the Telegram user ID as text, not a users.id FK
create table if not exists ui_configurations (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  environment text,
  api_base_url text,
  safe_area_top integer default 0,
  safe_area_bottom integer default 0,
  safe_area_left integer default 0,
  safe_area_right integer default 0,
  theme text,
  theme_source text,
  language text,
  language_source text,
  features jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists inline_analytics_daily (
  id uuid primary key default gen_random_uuid(),
  date date not null,
  chat_type text not null,
  trigger_counts jsonb default '{}'::jsonb,
  request_count integer default 0,
  success_count integer default 0,
  failure_count integer default 0,
  permission_block_count integer default 0,
  avg_ack_latency_ms integer default 0,
  p95_result_latency_ms integer default 0,
  accuracy_within_tolerance_pct double precision default 0.0,
  failure_reasons jsonb default '[]'::jsonb,
  last_updated_at timestamptz default now(),
  unique (date, chat_type)
);

create index if not exists idx_photos_user_created on photos(user_id, created_at);
create index if not exists idx_photos_meal_id on photos(meal_id);
create index if not exists idx_photos_media_group on photos(media_group_id);
create index if not exists idx_estimates_photo_ids on estimates using gin (photo_ids);
create index if not exists idx_meals_user_date on meals(user_id, meal_date);
create index if not exists idx_meals_user_created on meals(user_id, created_at desc);
create index if not exists idx_meals_created_at on meals(created_at);
-- one goal per user; replaces the old non-unique idx_goals_user_id
drop index if exists idx_goals_user_id;
create unique index if not exists idx_goals_user_id_unique on goals(user_id);
create index if not exists idx_feedback_user_id on feedback_submissions(user_id);
create index if not exists idx_feedback_status on feedback_submissions(status);
create index if not exists idx_feedback_type on feedback_submissions(message_type);
create index if not exists idx_feedback_created_at on feedback_submissions(created_at desc);

create or replace function update_updated_at_column() returns trigger
  language plpgsql security definer
  set search_path to 'public'
  as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists update_feedback_submissions_updated_at on feedback_submissions;
create trigger update_feedback_submissions_updated_at
  before update on feedback_submissions
  for each row execute function update_updated_at_column();

-- Used by services/statistics_service.py. p_end_date is exclusive.
-- No longer called by the app: statistics_service.py groups meals by the user's local
-- date (x-timezone header). Kept to mirror the live schema; safe to drop.
create or replace function query_daily_statistics(p_user_id uuid, p_start_date text, p_end_date text)
  returns table(
    meal_date date,
    total_calories numeric,
    total_protein numeric,
    total_fat numeric,
    total_carbs numeric,
    meal_count bigint
  )
  language plpgsql security definer
  set search_path to 'public'
  as $$
begin
  return query
  select
    m.meal_date,
    coalesce(sum(m.kcal_total), 0) as total_calories,
    coalesce(sum(m.protein_grams), 0) as total_protein,
    coalesce(sum(m.fats_grams), 0) as total_fat,
    coalesce(sum(m.carbs_grams), 0) as total_carbs,
    count(*)::bigint as meal_count
  from public.meals m
  where
    m.user_id = p_user_id
    and m.created_at >= p_start_date::timestamp with time zone
    and m.created_at < p_end_date::timestamp with time zone
  group by m.meal_date
  order by m.meal_date asc;
end;
$$;
