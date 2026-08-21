"""
TA Tenders — конфигурация пайплайна.

Секреты только из .env / переменных окружения (в GitHub Actions — Secrets).
Здесь — константы: реестры источников, ключевые слова, промпты, пороги.
Основа — uz-monitor-v2 (вариант A), доработано под сайт-агрегатор.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent          # корень репозитория
DATA_DIR = BASE_DIR / "data"
WEB_DATA_DIR = BASE_DIR / "web" / "data"
LOG_FILE = DATA_DIR / "monitor.log"
DB_FILE = DATA_DIR / "monitor.db"

# ─────────────────────────── Секреты ───────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
HEALTHCHECK_URL = os.getenv("HEALTHCHECK_URL", "")

# Базовый URL сайта — для кнопок «Разбор на сайте» в Telegram.
SITE_BASE_URL = os.getenv("SITE_BASE_URL", "").rstrip("/")

# ─────────────────────────── Поведение ───────────────────────────
MAX_AGE_DAYS = int(os.getenv("MAX_AGE_DAYS", "5"))    # свежесть новостей
NEAR_DUP_DAYS = 14                                     # окно семантического дедупа против истории
SEEN_NEWS_PRUNE_DAYS = 60                              # seen для новостей; тендеры/НПА — вечные
ANALYZE_MAX = int(os.getenv("ANALYZE_MAX", "60"))      # потолок LLM-анализов за один запуск (Haiku ≈ $0.01/шт)
TIMEZONE = "Asia/Tashkent"

MODEL_FILTER = os.getenv("MODEL_FILTER", "claude-haiku-4-5-20251001")
MODEL_ANALYZE = os.getenv("MODEL_ANALYZE", "claude-haiku-4-5-20251001")
# Аналитика пишется реже и должна быть качественной: сначала Sonnet, при ошибке — MODEL_ANALYZE.
MODEL_INSIGHT = os.getenv("MODEL_INSIGHT", "claude-sonnet-5")
MIN_SCORE_FOR_DEEP = 6
MIN_SCORE_FOR_NOTIFY = 7

# Аналитический дайджест НПА: генерируем, если с прошлого прошло ≥ INSIGHT_EVERY_DAYS
# и за период накопилось ≥ INSIGHT_MIN_LAW_ITEMS актов.
INSIGHT_EVERY_DAYS = int(os.getenv("INSIGHT_EVERY_DAYS", "6"))
INSIGHT_MIN_LAW_ITEMS = int(os.getenv("INSIGHT_MIN_LAW_ITEMS", "3"))
INSIGHT_LOOKBACK_DAYS = int(os.getenv("INSIGHT_LOOKBACK_DAYS", "7"))

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
HTTP_TIMEOUT = 25

# ─────────────────────────── Категории ───────────────────────────
CAT_INTL = "international_tender"    # тендеры МФО / доноров
CAT_UZTEND = "uz_tender"             # тендеры Узбекистана
CAT_JOB = "job"                      # позиции индивидуальных консультантов
CAT_NEWS = "news"                    # деловые новости
CAT_LAW = "legislation"              # НПА и проекты НПА

CATEGORY_TITLE = {
    CAT_INTL: "🌍 Международные тендеры",
    CAT_UZTEND: "🇺🇿 Тендеры Узбекистана",
    CAT_JOB: "🧑‍💼 Позиции / эксперты",
    CAT_LAW: "⚖️ Законодательство",
    CAT_NEWS: "📰 Новости",
}
CATEGORY_ORDER = [CAT_INTL, CAT_UZTEND, CAT_JOB, CAT_LAW, CAT_NEWS]
# На сайт тендеры/НПА/позиции идут ВСЕ; новости — только с высокой оценкой.
SITE_MIN_NEWS_SCORE = 7

# ─────────────────────────── Новостные RSS (рабочие, июль 2026) ───────────────────────────
RSS_FEEDS = [
    {"name": "Gazeta.uz",        "url": "https://www.gazeta.uz/ru/rss/",                  "dir": "новости"},
    {"name": "Gazeta Экономика", "url": "https://www.gazeta.uz/ru/rss/?section=economy",  "dir": "экономика"},
    {"name": "Spot.uz",          "url": "https://www.spot.uz/ru/rss/",                    "dir": "бизнес"},
    {"name": "Kun.uz",           "url": "https://kun.uz/news/rss",                        "dir": "новости"},
    {"name": "UzDaily EN",       "url": "https://uzdaily.uz/en/rss",                      "dir": "экономика"},
    {"name": "Review.uz",        "url": "https://review.uz/rss",                          "dir": "аналитика"},
    {"name": "Podrobno.uz",      "url": "https://podrobno.uz/rss/",                       "dir": "новости"},
    {"name": "Nuz.uz",           "url": "https://nuz.uz/feed/",                           "dir": "новости"},
    {"name": "UzA.uz",           "url": "https://uza.uz/ru/rss",                          "dir": "официальные"},
    {"name": "Tashkent Times",   "url": "https://tashkenttimes.uz/?format=feed&type=rss", "dir": "англ_новости"},
]

MFI_RSS_FEEDS = [
    {"name": "AIIB Procurement", "url": "https://www.aiib.org/en/rss/aiib-project-procurements-rss.xml"},
]

# ─────────────────────────── World Bank Procurement API ───────────────────────────
WB_API_URL = "https://search.worldbank.org/api/v2/procnotices"
WB_API_FIELDS = ("id,notice_type,noticedate,submission_deadline_date,project_ctry_name,"
                 "project_id,project_name,bid_description,bid_reference_no,"
                 "procurement_method_name,notice_text")
WB_NOTICE_TYPES_KEEP = {
    "Request for Expression of Interest",
    "General Procurement Notice",
    "Invitation for Bids",
    "Request for Bids",
}

# ─────────────────────────── EU TED API ───────────────────────────
TED_ENABLED = os.getenv("TED_ENABLED", "1") == "1"
TED_API_URL = "https://api.ted.europa.eu/v3/notices/search"
TED_QUERY = ('(place-of-performance IN (UZB KAZ KGZ TJK TKM) OR '
             'text ~ ("Uzbekistan" "Central Asia")) AND contract-nature = services')
TED_FIELDS = ["publication-number", "notice-title", "place-of-performance",
              "publication-date", "deadline-receipt-request", "links", "buyer-name"]

# ─────────────────────────── UNDP ───────────────────────────
UNDP_URL = "https://procurement-notices.undp.org/"

# ─────────────────────────── TenderWeek (публичный листинг) ───────────────────────────
# ВАЖНО: логин на TenderWeek закрыт reCAPTCHA — автоматизировать вход нельзя.
# Листинг главной страницы ПУБЛИЧНЫЙ и содержит: заказчик, №, название, описание,
# категорию и дату. Полные тексты этих же тендеров даёт первоисточник (etender/xarid).
TENDERWEEK_URL = "https://www.tenderweek.com/"
TENDERWEEK_PAGES = int(os.getenv("TENDERWEEK_PAGES", "10"))  # главная + ?page=2..N (лента уходит в архив быстро)

# ─────────────────────────── Headless (JS-SPA через Playwright) ───────────────────────────
HEADLESS_ENABLED = os.getenv("HEADLESS_ENABLED", "0") == "1"
HEADLESS_ON = [x.strip() for x in os.getenv("HEADLESS_ON", "etender,xtxarid,ebrd,ungm").split(",") if x.strip()]
HEADLESS_MAX = int(os.getenv("HEADLESS_MAX", "120"))
ETENDER_LIST_URL = os.getenv("ETENDER_LIST_URL", "https://etender.uzex.uz/lots/1/0")

HEADLESS_SOURCES = [
    {"key": "etender", "source": "UZEX e-Tender (конкурс)", "origin": "etender.uzex.uz",
     "cat": CAT_UZTEND, "url": ETENDER_LIST_URL,
     "detail_url": "https://etender.uzex.uz/lot/{id}", "consulting_only": True},
    {"key": "xtxarid", "source": "XT-Xarid (госзакупки)", "origin": "xt-xarid.uz",
     "cat": CAT_UZTEND, "url": os.getenv("XTXARID_LIST_URL", "https://xt-xarid.uz/"),
     "detail_url": "https://xt-xarid.uz/procedure/{id}/core",
     "prefer_key": "lot_count",   # уровень процедуры (id для ссылки), не позиций внутри неё
     "consulting_only": True},
    {"key": "ebrd", "source": "EBRD ECEPP", "origin": "ecepp.ebrd.com",
     "cat": CAT_INTL,
     "url": "https://ecepp.ebrd.com/delta/noticeSearchResults.html",
     "consulting_only": True},
    # UNGM — агрегатор закупок ВСЕЙ системы ООН (ПРООН, МОТ, IOM, FAO, ЮНИСЕФ, WFP…).
    # Список грузится после клика «Search» → свой сценарий (custom) в headless.py.
    {"key": "ungm", "source": "UNGM (система ООН)", "origin": "ungm.org",
     "cat": CAT_INTL, "url": "https://www.ungm.org/Public/Notice", "custom": "ungm"},
    # Кандидаты (SPA, generic-перехват; включаются добавлением ключа в HEADLESS_ON):
    {"key": "tenderasia", "source": "Tender.asia (агрегатор УЗ)", "origin": "tender.asia",
     "cat": CAT_UZTEND, "url": "https://tender.asia/", "consulting_only": True},
    {"key": "shaffof", "source": "ShaffofXarid (открытые закупки)", "origin": "shaffofxarid.uz",
     "cat": CAT_UZTEND, "url": "https://shaffofxarid.uz/", "consulting_only": True},
    {"key": "regulation", "source": "regulation.gov.uz (проекты НПА)", "origin": "regulation.gov.uz",
     "cat": CAT_LAW, "url": os.getenv("REGULATION_URL", "https://regulation.gov.uz/ru"),
     "require_signal": False},
]

# Страны для поиска на UNGM (фильтр «Beneficiary country»)
UNGM_COUNTRIES = [c.strip() for c in os.getenv(
    "UNGM_COUNTRIES",
    "Uzbekistan,Kyrgyzstan,Tajikistan,Kazakhstan,Turkmenistan").split(",") if c.strip()]

# ─────────────────────────── uzjobs.uz — вакансии консультантов (RSS) ───────────────────────────
UZJOBS_RSS = "https://www.uzjobs.uz/rss_vak.cgi"
JOB_KEYWORDS = [
    "консультант", "consultant", "маслаҳатчи", "maslahatchi",
    "эксперт", "expert", "advisor", "советник",
    "аналитик", "analyst", "юрист", "legal", "lawyer",
    "project officer", "программный специалист",
]

# ─────────────────────────── Фильтры-словари ───────────────────────────
REGION_KEYWORDS = [
    "uzbekistan", "ouzbékistan", "usbekistan", "узбекистан", "oʻzbekiston", "uzbek",
    "central asia", "asie centrale", "zentralasien", "центральная азия",
    "tashkent", "samarkand", "bukhara", "namangan", "andijan", "fergana",
    "tajikistan", "tajik", "таджикистан", "kyrgyz", "кыргыз", "киргиз",
    "kazakhstan", "kazakh", "казахстан", "turkmenistan", "туркменистан",
    "dushanbe", "bishkek", "almaty", "astana",
]

CONSULTING_KEYWORDS = [
    "konsalting", "консалтинг", "konsultats", "консультац", "konsultativ", "консультатив",
    "maslahat", "маслаҳат", "маслахат", "audit", "аудит", "strategi", "стратеги",
    "tadqiqot", "тадқиқот", "исследован", "loyiha", "лойиҳа", "loyihalash", "проектн",
    "feasibility", "texnik-iqtisodiy", "texnik iqtisodiy", "тэо", "biznes-reja",
    "бизнес-режа", "due diligence", "konsultant", "консультант",
    "consultanc", "consulting", "advisor", "advisory", "supervision",
    "technical assistance", "technical cooperation", "capacity building",
    "project implementation support", " pis ",
    # ИТ-услуги — профиль «разработка ИС» (LLM-фильтр отсеет нерелевантное)
    "разработк", "внедрени", "автоматизирован", "информационн", "программн",
    "цифров", "техническ", "поддержк", "сопровожден",
    "dasturiy", "axborot tizim", "avtomatlash", "raqamli", "ishlab chiq",
    "software", "information system", "digital",
]

# ─────────────────────────── Исключения: закупки товаров/оборудования ───────────────────────────
# Мы консалтинг: поставки техники, стройматериалов, мебели, продуктов — не наш профиль.
# Отсекаются на входе (до LLM), если в названии есть товарный маркер и НЕТ услугового.
GOODS_KEYWORDS = [
    "поставк", "закупка оборудован", "закуп ", "приобретение", "оборудовани", "техник",
    "инструмент", "материал", "металлопрокат", "мебел", "запасн", "запчаст", "топлив",
    "продукт", "продовольств", "автомобил", "транспортн", "спецтехник", "реагент",
    "огнетушител", "манометр", "кабел", "труб", "краск", "грунтовк", "сиз ", "спецодежд",
    "компьютер", "мфу", "принтер", "сервер", "сетевое оборудование", "лаборатор",
    "медицинск", "лекарств", "камер", "сканер", "lidar", "балансировщик",
    "supply of", "procurement of", "invitation for bids", "itb ", "goods", "equipment",
    "vehicles", "furniture", "materials", "spare parts", "delivery of",
    "jihoz", "uskuna", "xarid qilish", "yetkazib berish", "mahsulot", "texnika",
]
# Услуговые маркеры, которые «спасают» запись даже при товарном слове в названии.
SERVICE_KEYWORDS = [
    "консульт", "consult", "услуг", "service", "разработк", "внедрен", "автоматиз",
    "информационн", "программн", "software", "it-", "ит-", "аудит", "audit", "стратег",
    "исследован", "study", "assessment", "оценк", "тэо", "feasibility", "проектиров",
    "design", "supervision", "надзор", "обучен", "training", "capacity", "technical assistance",
    "техсодейств", "expression of interest", "reoi", "eoi", "individual consultant",
    "advisor", "эксперт", "юрид", "legal", "maslahat", "konsalting", "dasturiy", "axborot tizim",
]

# ─────────────────────────── Профиль компании ───────────────────────────
COMPANY_PROFILE = """КОНСАЛТИНГОВАЯ КОМПАНИЯ (Узбекистан). Направления:
1. Цифровая трансформация: ИС для госорганов, электронное правительство, интеграция данных.
2. Энергоконсалтинг: энергоаудит, ВИЭ (солнечная), ESCO, финмоделирование.
3. Техсодействие МФО: управление проектами ЕС/ЕБРР/АБР/ВБ, заявки на гранты.
4. Стратегическое планирование: стратегии развития, дорожные карты, ISO, EFQM.
5. Инвестконсалтинг: ТЭО, due diligence, привлечение инвестиций.
6. Регуляторный/юридический консалтинг: анализ НПА, compliance, правовая экспертиза."""

# ─────────────────────────── Промпт фильтра ───────────────────────────
FILTER_PROMPT = """Ты — СТРОГИЙ фильтр релевантности для консалтинговой компании в Узбекистане.
Оцени КАЖДЫЙ элемент по шкале 1–10: реальная ли это коммерческая возможность.

ВЫСОКО (7–10) — только если есть конкретный заказчик/проект/тендер/НПА И прямая
возможность продать услугу (консалтинг, ТА, ИС, аудит, стратегия, юрид. сопровождение):
- «ЕБРР объявил тендер на консультанта для проекта в Намангане» → 9
- «Минцифры запускает цифровизацию кадастра за $10 млн» → 9
- «World Bank: Request for Expression of Interest — consulting in Uzbekistan» → 10
- «Принят указ об обязательном энергоаудите промпредприятий» → 8

ВАЖНО: разработка/внедрение информационных систем и АСУ, автоматизация,
техподдержка ПО — это ПРОФИЛЬНОЕ направление компании (цифровая трансформация).
Госзакупки таких услуг — реальные возможности:
- «Госзакупка: разработка и внедрение автоматизированной системы управления» → 8
- «Тендер: техническая поддержка ПО / информационных систем госоргана» → 7
- «Закупка программного решения для инфраструктуры аэропортов» → 8

НИЗКО (1–3) — безжалостно отсекай:
- Мировые новости без Узбекистана, аналитика, мнения, макростатистика (ВВП, курсы) → 1
- Общие совещания без конкретных проектов/бюджетов → 2
- Розница, спорт, погода, криминал; закупка товаров/стройматериалов без ИТ/консалтинга → 1

ИСКЛЮЧЕНИЕ: тендеры МФО (World Bank, EBRD, ADB, UNDP, AIIB, IsDB) на консалтинг/ТА,
связанные с Узбекистаном или ЦА, — автоматически 9–10.

Тебе дан СПИСОК элементов (JSON). Верни ТОЛЬКО JSON-массив той же длины и порядка:
[{"i": <индекс>, "score": <1-10>, "reason": "<кратко>"}, ...]"""

# ─────────────────────────── Промпт анализа (для карточки сайта и Telegram) ───────────────────────────
ANALYSIS_PROMPT = """Ты — старший бизнес-аналитик консалтинговой компании в Узбекистане.
Проанализируй новость/тендер/НПА и дай практический разбор.

ЯЗЫК: все текстовые поля — ВСЕГДА на русском (переводи суть, не копируй оригинал).
ФАКТЫ: используй только факты из текста источника; если данных нет — null.
Не придумывай суммы, сроки и названия.

{company_profile}

ИСТОЧНИК: {source} ({category})
Заголовок: {title}
URL: {url}
Текст: {text}

Верни ТОЛЬКО JSON (без markdown, без пояснений):
{{
  "title_ru": "<чёткий короткий заголовок НА РУССКОМ, 5–10 слов>",
  "summary_ru": "<2–3 предложения: ЧТО закупается/происходит, КТО заказчик, СКОЛЬКО, срок — только факты>",
  "site_brief": "<развёрнутый разбор для сайта, 4–6 предложений: контекст, что именно потребуется исполнителю, на что обратить внимание>",
  "relevance_score": <1-10>,
  "opportunity_type": "<консалтинг|техсодействие|разработка_ИС|стратегия|аудит|тендер|юрид_сопровождение|нет>",
  "target_entity": "<заказчик/организация из текста или null>",
  "budget_info": "<сумма из текста или null>",
  "deadline_info": "<срок подачи из текста (ГГГГ-ММ-ДД если возможно) или null>",
  "npa_ref": "<реквизит НПА, если упоминается конкретный акт (напр. «ЗРУ-1137», «ПП-394», «УП-60») или null>",
  "eligibility": "<требования к участникам из текста (опыт, обороты, лицензии) или null>",
  "docs_checklist": ["<список документов для подачи, только если перечислены в тексте>"],
  "consulting_recommendation": "<конкретная услуга, которую можно предложить, 1 предложение>",
  "legal_aspects": ["<юридические аспекты: что требуется по закону, риски, комплаенс — только если следуют из текста, 0–3 пункта>"],
  "action_items": ["<конкретные шаги для участия: с кем связаться, что подготовить, 0–3 пункта — только из текста>"],
  "contact_suggestion": "<контакт/ведомство для связи из текста или null>",
  "urgency": "<критическая|высокая|средняя|низкая>"
}}"""

# ─────────────────────────── Промпт аналитического дайджеста НПА ───────────────────────────
INSIGHT_PROMPT = """Ты — старший юрист-аналитик консалтинговой компании в Узбекистане.
Ниже — новые нормативно-правовые акты за период {period} (и связанные новости).
Напиши РЕГУЛЯТОРНЫЙ ДАЙДЖЕСТ — готовый аналитический материал для публикации
на сайте компании: деловой, конкретный, без воды и канцелярита.

ЖЁСТКИЕ ПРАВИЛА:
- Только факты из предоставленных текстов. Никаких выдуманных номеров, сумм, дат.
- Если из текста непонятна суть акта — не упоминай его вовсе.
- Весь текст НА РУССКОМ (переводи узбекские названия по смыслу).
- Реквизиты актов указывай как в данных (напр. «ПП-289», «ЗРУ-1126»).
- Группируй акты по темам (экономика/финансы, госуправление/цифра, социалка и т.д.),
  а не перечисляй подряд.

ДАННЫЕ:
{acts}

Верни ТОЛЬКО JSON:
{{
  "title": "<заголовок дайджеста, ёмкий, с периодом>",
  "lead": "<лид 2–3 предложения: главное за период>",
  "sections": [
    {{"heading": "<тема>", "body": "<3–6 предложений: что принято, что меняется, для кого>",
      "act_keys": ["<реквизиты упомянутых актов>"]}}
  ],
  "business_impact": ["<3–5 пунктов: что это значит для бизнеса — конкретно>"],
  "how_to_prepare": ["<3–4 практических шага: что стоит сделать компаниям>"]
}}"""
