-- TA Tenders — миграция 002: надёжное сохранение + история действий.
-- Выполнить в Supabase: SQL Editor → New query → вставить → Run.

-- 1. Убираем внешний ключ на tenders: контент живёт в web/data, таблица tenders
--    лишь зеркало и может отставать — из-за FK сохранения молча отклонялись.
alter table public.tender_state drop constraint if exists tender_state_tender_id_fkey;

-- 2. История всех действий команды (кто, что, с каким тендером, когда).
create table if not exists public.activity_log (
  id bigserial primary key,
  user_id uuid references auth.users(id) on delete set null,
  tender_id text not null,
  tender_title text,
  action text not null,           -- status | saved | unsaved | note
  value text,                     -- новый статус / текст заметки
  created_at timestamptz default now()
);
create index if not exists idx_activity_tender on public.activity_log(tender_id, created_at desc);
create index if not exists idx_activity_user on public.activity_log(user_id, created_at desc);

alter table public.activity_log enable row level security;
create policy "activity: read team" on public.activity_log
  for select to authenticated using (true);
create policy "activity: insert own" on public.activity_log
  for insert to authenticated with check (auth.uid() = user_id);
