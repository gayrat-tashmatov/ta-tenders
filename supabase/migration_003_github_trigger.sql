-- Запуск пайплайна по точному расписанию через Supabase (pg_cron + pg_net → GitHub API).
-- Зачем: cron самого GitHub для этого репо срабатывает только 3 раза в сутки
-- (~07:40, ~13:30, ~18:15 UTC) при любом выражении в monitor.yml — проверено 11–24.09.2026.
--
-- Перед запуском: GitHub → Settings → Developer settings → Fine-grained tokens →
--   Generate: Repository access = ta-tenders; Permissions → Actions: Read and write.
-- Токен вставить ТОЛЬКО сюда (в Vault), в чат/файлы не копировать:
--   select vault.create_secret('github_pat_XXXX', 'github_pat');

create extension if not exists pg_cron;
create extension if not exists pg_net;

select cron.unschedule('ta-tenders-monitor') where exists
  (select 1 from cron.job where jobname = 'ta-tenders-monitor');

-- 07:17, 10:17, 13:17, 16:17, 19:17, 22:17 по Ташкенту (UTC+5)
select cron.schedule(
  'ta-tenders-monitor',
  '17 2,5,8,11,14,17 * * *',
  $$
  select net.http_post(
    url     := 'https://api.github.com/repos/gayrat-tashmatov/ta-tenders/actions/workflows/monitor.yml/dispatches',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || (select decrypted_secret from vault.decrypted_secrets where name = 'github_pat' limit 1),
      'Accept', 'application/vnd.github+json',
      'Content-Type', 'application/json',
      'User-Agent', 'supabase-cron'),
    body    := '{"ref":"main"}'::jsonb
  );
  $$
);

-- Проверка: select * from cron.job;  select * from cron.job_run_details order by start_time desc limit 5;
-- Ответ GitHub (204 = ок): select status_code, created from net._http_response order by created desc limit 5;
