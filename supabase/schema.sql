-- TA Tenders — схема кабинета. Выполнить один раз в Supabase: SQL Editor → New query → вставить → Run.

-- 1. Тендеры (заливает пайплайн сервисным ключом; команда только читает)
create table if not exists public.tenders (
  id text primary key,                -- slug пайплайна (wb-op…, tw-…, lexuz-…)
  uid text, category text, source text, origin text,
  title text, title_ru text, url text,
  published timestamptz, deadline date, buyer text, budget text,
  score int, urgency text,
  summary_ru text, site_brief text, eligibility text,
  docs_checklist jsonb default '[]', recommendation text,
  npa_refs jsonb default '[]',
  first_seen timestamptz default now(),
  updated_at timestamptz default now()
);
create index if not exists idx_tenders_category on public.tenders(category);
create index if not exists idx_tenders_deadline on public.tenders(deadline);
create index if not exists idx_tenders_first_seen on public.tenders(first_seen desc);

-- 2. Профили команды (создаются триггером при добавлении пользователя)
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  telegram_chat_id text               -- для персональных уведомлений (фаза 2)
);

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, full_name)
  values (new.id, coalesce(new.raw_user_meta_data->>'full_name', split_part(new.email, '@', 1)))
  on conflict (id) do nothing;
  return new;
end $$;
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users for each row execute function public.handle_new_user();

-- 3. Личное состояние по тендеру (статус, звёздочка, заметка)
create table if not exists public.tender_state (
  user_id uuid references auth.users(id) on delete cascade,
  tender_id text references public.tenders(id) on delete cascade,
  status text not null default 'new'
    check (status in ('new','viewed','working','submitted','won','lost','skipped')),
  saved boolean not null default false,
  note text,
  updated_at timestamptz default now(),
  primary key (user_id, tender_id)
);
create index if not exists idx_state_tender on public.tender_state(tender_id);

-- 4. Доступ: команда 3–4 человека — все читают всё, пишут только своё
alter table public.tenders enable row level security;
create policy "tenders: read" on public.tenders
  for select to authenticated using (true);

alter table public.profiles enable row level security;
create policy "profiles: read team" on public.profiles
  for select to authenticated using (true);
create policy "profiles: update own" on public.profiles
  for update to authenticated using (auth.uid() = id);

alter table public.tender_state enable row level security;
create policy "state: read team" on public.tender_state
  for select to authenticated using (true);          -- видно, кто ведёт тендер
create policy "state: insert own" on public.tender_state
  for insert to authenticated with check (auth.uid() = user_id);
create policy "state: update own" on public.tender_state
  for update to authenticated using (auth.uid() = user_id);
create policy "state: delete own" on public.tender_state
  for delete to authenticated using (auth.uid() = user_id);
