# TA Tenders — агрегатор тендеров, донорских проектов и НПА

Публичный сайт + Telegram-канал для TopAdvisor: международные тендеры МФО
(Всемирный банк, TED/ЕС, UNDP, AIIB, ЕБРР), госзакупки Узбекистана
(TenderWeek, etender.uzex.uz), позиции экспертов и мониторинг законодательства
(lex.uz) — с LLM-разбором каждой позиции.

**Архитектура — полностью serverless, без VPS:**

```
GitHub Actions (cron 4×/день)
  └─ pipeline/ (Python): сбор → дедуп v3 → Haiku-фильтр → анализ карточек
       ├─ data/monitor.db      (SQLite, коммитится — «репо как база»)
       ├─ web/data/*.json      (экспорт для сайта, коммитится)
       │     └─ push → Vercel автосборка сайта (web/, Next.js SSG)
       └─ Telegram: короткие карточки + кнопка «Разбор на сайте»
```

Наследует uz-monitor-v2 (`TopAdvisor/7. News Database/`), главные отличия:
дедуп против истории и между категориями, вечный реестр НПА по реквизиту акта
(один акт = одна карточка, новости прикрепляются упоминаниями — повторов нет),
экспорт на сайт, хостинг без сервера.

## Локальный запуск

```bash
# Пайплайн
cd pipeline
cp .env.example .env          # заполнить ключи
pip install -r requirements.txt
python3 run.py --test         # проверка источников (шлёт тест в Telegram, если задан)
python3 run.py --collect      # только сбор, без LLM и Telegram
python3 run.py --run --no-telegram   # полный цикл без отправки
python3 run.py --run          # боевой цикл

# Сайт
cd ../web
npm install
npm run dev                   # http://localhost:3000
```

Без `ANTHROPIC_API_KEY` пайплайн работает в dry-режиме (эвристический скоринг).
`ANALYZE_MAX` в .env ограничивает число LLM-разборов за запуск (контроль затрат).

## Развёртывание (один раз)

1. **Перевыпустить ключи** — старые Telegram/Anthropic-токены из
   `7. News Database/News database/` скомпрометированы (лежали открытым текстом).
2. Создать **приватный GitHub-репозиторий**, запушить этот проект.
3. **Vercel** → Add New Project → импортировать репозиторий,
   Root Directory = `web`. Задеплоится статикой.
4. GitHub → Settings → Secrets → Actions: `ANTHROPIC_API_KEY`,
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SITE_BASE_URL`
   (URL сайта с Vercel), опц. `HEALTHCHECK_URL` (healthchecks.io).
5. Actions → workflow `monitor` → Run workflow (первый прогон вручную).
   Дальше — по расписанию 4×/день; каждый прогон коммитит данные,
   и Vercel пересобирает сайт автоматически.

Лимиты бесплатных тарифов: GitHub Actions 2000 мин/мес (4 прогона/день по
~6 мин ≈ 750 мин — с запасом), Vercel Hobby формально некоммерческий — для
прода перейти на Pro ($20/мес) или Cloudflare Pages (бесплатно, коммерческое ок).

## Источники

| Источник | Доступ | Категория |
|---|---|---|
| World Bank Procurement API | официальный JSON API | 🌍 |
| EU TED API | официальный API (флаг `TED_ENABLED`) | 🌍 |
| UNDP Procurement | HTML, requests | 🌍 |
| AIIB Procurement | RSS + фильтр региона | 🌍 |
| EBRD ECEPP | headless (Playwright, перехват JSON) | 🌍 |
| TenderWeek | **публичный листинг** (логин закрыт reCAPTCHA — не автоматизируем) | 🇺🇿 |
| etender.uzex.uz, xt-xarid | headless (конкурсы = консалтинг) | 🇺🇿 |
| lex.uz (`t.me/s/lexuzofficial`) | публичный Telegram-канал | ⚖️ |
| 10 новостных RSS | Gazeta, Spot, Kun, UzDaily, … | 📰 |

## Дедупликация (v3)

1. **Вечный seen** по стабильным ключам: uid источника (`wb:OP…`, `tw:36300`,
   `lexuz:<id>`) → канонический URL → контент-хеш. Тендеры и НПА не протухают;
   новостные хеши чистятся через 60 дней.
2. **Реестр НПА** по реквизиту акта (`ZRU-1137`, `UP-60`, `PP-394`, `PKM-…`,
   `LEX-<id>`), извлекается regex-ом + LLM-полем `npa_ref` из любых категорий.
   Известный акт → новость становится «упоминанием» карточки, не новой записью.
3. **Семантический дедуп** (перекрытие токенов ≥ 0.45) против истории за 14 дней
   и между категориями news↔legislation, плюс внутри запуска.
