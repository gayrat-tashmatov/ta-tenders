"""
TA Tenders — конфигурация пайплайна.

Секреты только из .env / переменных окружения (в GitHub Actions — Secrets).
Здесь — константы: реестры источников, ключевые слова, промпты, пороги.
Основа — uz-monitor-v2 (вариант A), доработано под сайт-агрегатор.
"""

import os
import re
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
# Личный чат эксперта (Гайрат): позиции для индивидуального консультанта дублируются туда.
# Узнать id: написать боту /start, затем getUpdates. Пусто — только в канал.
def _chat_id(raw: str) -> str:
    """Из значения секрета берём сам id: в секрет часто вставляют всю строку «NAME = 123» (15.10.2026)."""
    m = re.search(r"-?\d{5,}|@\w{4,}", raw or "")
    return m.group(0) if m else ""


TELEGRAM_EXPERT_CHAT = _chat_id(os.getenv("TELEGRAM_EXPERT_CHAT_ID", ""))
# Утренняя сводка «Сегодня в кабинете» — один раз в день после этого часа по Ташкенту.
MORNING_HOUR_TASHKENT = int(os.getenv("MORNING_HOUR_TASHKENT", "7"))
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
MODEL_INSIGHT = os.getenv("MODEL_INSIGHT", "claude-opus-5-5")   # недельный обзор (до 15.10 — Sonnet 5, «сырой»)
MODEL_ACT = os.getenv("MODEL_ACT", "claude-opus-5-5")           # разбор каждого значимого акта по полному тексту
ACT_REVIEW_MAX = int(os.getenv("ACT_REVIEW_MAX", "25"))         # разборов актов за прогон (~$0,06 за акт)
ACT_MIN_FILTER_SCORE = int(os.getenv("ACT_MIN_FILTER_SCORE", "4"))  # ниже — акт без разбора (узкие ведомственные)
MIN_SCORE_FOR_DEEP = 6
MIN_SCORE_FOR_NOTIFY = 7

# Аналитический дайджест НПА: генерируем, если с прошлого прошло ≥ INSIGHT_EVERY_DAYS
# и за период накопилось ≥ INSIGHT_MIN_LAW_ITEMS актов.
INSIGHT_EVERY_DAYS = int(os.getenv("INSIGHT_EVERY_DAYS", "7"))   # недельный обзор (до 15.10 — ежедневный «недельный» на скользящем окне)
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
                 "procurement_method_name,procurement_method_code,notice_text")
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
HEADLESS_ON = [x.strip() for x in os.getenv("HEADLESS_ON", "ebrd,ungm").split(",") if x.strip()]
HEADLESS_MAX = int(os.getenv("HEADLESS_MAX", "120"))
ETENDER_LIST_URL = os.getenv("ETENDER_LIST_URL", "https://etender.uzex.uz/lots/1/0")
# etender: прямой API списка (POST TradeList, пагинация From/To). Лента отсортирована
# по ДАТЕ ОКОНЧАНИЯ — первые 20 = закрывающиеся сегодня. Поэтому берём всю ленту.
ETENDER_API_URL = "https://apietender.uzex.uz/api/common/TradeList"
ETENDER_API_MAX = int(os.getenv("ETENDER_API_MAX", "3000"))   # лента > 600 с октября: новые лоты (дальний дедлайн) в хвосте     # активных лотов за раз
# Telegram: не слать лоты, у которых до дедлайна меньше N часов — не успеть.
NOTIFY_MIN_HOURS_LEFT = int(os.getenv("NOTIFY_MIN_HOURS_LEFT", "24"))
NOTIFY_LAW_MAX_AGE_DAYS = int(os.getenv("NOTIFY_LAW_MAX_AGE_DAYS", "7"))  # НПА старше N дней — на сайт и в реестр, но не в канал (догон после простоя)

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

# Чужие регионы: международные извещения, где явно названа страна вне ЦА и НЕ названа наша.
OFFREGION_KEYWORDS = [
    # Африка
    "nigeria", "kenya", "ethiopia", "tanzania", "uganda", "ghana", "senegal", "mali", "niger ",
    "burkina", "benin", "togo", "cameroon", "cameroun", "tchad", "chad ", "sudan", "somalia",
    "zimbabwe", "zambia", "malawi", "mozambique", "angola", "rwanda", "burundi", "congo",
    "madagascar", "sierra leone", "liberia", "guinea", "gambia", "côte d", "cote d", "ivoire",
    "south africa", "lesotho", "eswatini", "botswana", "namibia", "djibouti", "eritrea",
    "morocco", "maroc", "algeria", "tunisia", "tunisie", "libya", "egypt", "égypte", "mauritania",
    "africa", "afrique", "ouidah", "dakar", "nairobi", "lagos", "kampala", "addis",
    # Латинская Америка и Карибы
    "brazil", "brasil", "argentina", "chile", "peru", "perú", "colombia", "bolivia", "ecuador",
    "venezuela", "paraguay", "uruguay", "mexico", "méxico", "guatemala", "honduras", "nicaragua",
    "el salvador", "costa rica", "panama", "panamá", "cuba", "haiti", "haïti", "dominican",
    "jamaica", "guyana", "suriname", "latin america", "américa latina", "caribbean", "caribe",
    # Прочая Азия/Океания/Ближний Восток вне ЦА
    "philippines", "maasin", "cagayan", "sorsogon", "indonesia", "vietnam", "viet nam",
    "cambodia", "myanmar", "thailand", "bangkok", "bangladesh", "sri lanka", "nepal", "bhutan",
    "pakistan", "india ", "papua", "fiji", "timor", "mongolia", "palestin", "gaza", "yemen",
    "iraq", "syria", "lebanon", "jordan", "libya", "afghanistan",
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
    "поставк", "закупка оборудован", "закуп ", "приобретение", "оборудовани",
    # «техник» целиком — нельзя: режет «техническое обследование», «техник-иқтисодий асос», «Техник топшириқ»
    "техника", "техники", "оргтехник", "вычислительн",
    "инструмент", "материал", "металлопрокат", "мебел", "запасн", "запчаст", "топлив",
    "продукт", "продовольств", "автомобил", "транспортн", "спецтехник", "реагент",
    "огнетушител", "манометр", "кабел", "труб", "краск", "грунтовк", "сиз ", "спецодежд",
    "компьютер", "мфу", "принтер", "сервер", "сетевое оборудование", "лаборатор",
    "медицинск", "лекарств", "камер", "сканер", "lidar", "балансировщик",
    "supply of", "procurement of", "invitation for bids", "itb ", "goods", "equipment",
    "vehicles", "furniture", "materials", "spare parts", "delivery of",
    # узбекские формы. «xarid qilish» («закупить») стоит в КАЖДОМ лоте etender, в т.ч.
    # «...xizmatini xarid qilish» — 14.09 из-за него улетело ТЭО (TIA). Убрано.
    "jihoz", "uskuna", "yetkazib berish", "mahsulot", "texnika", "avtomobil", "avtovoz",
    "mebel", "qurilma", "ehtiyot qism", "kompyuter", "printer", "kabel", "quvur", "boyoq",
    "oziq-ovqat", "dori-darmon", "yoqilgi", "kanselyariya", "материаллар", "жиҳоз", "ускуна",
    "маҳсулот", "автомобил", "мебел",
    # пропущенные ранее формы (21.08 → 03.09: «Закупка авто», «планшетов», «канцелярии»)
    "закупка ", "закупку ", "приобретен", "оснащен", "планшет", "ноутбук", "смартфон",
    "канцеляр", "стеллаж", "дезинфекц", "автотранспорт", "автобус", "трактор", "станок",
    "терминал", "лифт", "elevator", "техническая поддержка и обслуживание оборудования", "maintenance services for ict equipment",
    "construction of", "renovation", "rehabilitation of", "civil works", "строительств", "ремонт",
    "qurilish", "tamirlash", "қурилиш", "таъмирлаш",
    "medicines", "vaccine", "blood", "catering", "hotel", "restauration", "printing", "печат",
    "insurance", "internet services", "firewall", "translation", "photography", "videography",
    "modernization of", "modernisation of", "construction works", "installation and commissioning",
    "supply, installation", "protective fencing", "solar systems", "pumping station", "photovoltaic",
]
# Услуговые маркеры, которые «спасают» запись даже при товарном слове в названии.
# Тематики, которые НИКОГДА не профиль (до модели, по заголовку тендера; 15.10.2026).
# Услуговые слова не спасают: «Consulting Services to Support WHO in Enteric Vaccine R&D».
OFFPROFILE_KEYWORDS = [
    "vaccin", "immuniz", "immunis", "clinical", "tuberculos", " tb ", " hiv", "hiv/", "malaria",
    "epidemiolog", "seroepidem", "pharmaceutical", "drug-resistant", "drug-sensitive",
    "medical services", "veterinar", "peste des petits", "livestock disease",
    "cleaning service", "cleaning services", "copy-edit", "copyedit", "proofread",
    "telemarketing", "rental of premises", "premises for", "catering", "air tickets",
    "travel agency", "security guard", "guard services", "video production",
    "вакцин", "иммуниз", "клиническ", "туберкул", " вич", "вич-", "малярия", "эпидемиолог",
    "ветеринар", "уборк", "клининг", "аренда помещ", "охранные услуги", "авиабилет",
]

SERVICE_KEYWORDS = [
    "консульт", "consult", "услуг", "services", "service provider", "разработк", "внедрен", "автоматиз",
    "development of", "information system", "digital platform", "web portal", "database", "e-gov",
    "информационн", "программн", "software", "it-", "ит-", "аудит", "audit", "стратег",
    "исследован", "study", "assessment", "оценк", "тэо", "feasibility", "проектиров",
    "design", "supervision", "надзор", "обучен", "training", "capacity", "technical assistance",
    "техсодейств", "expression of interest", "reoi", "eoi", "individual consultant",
    "advisor", "эксперт", "юрид", "legal", "call for external collaborator",
    "обследовани", "сертификац", "экспертиз", "методик", "испытани", "техническое задание",
    # узбекский (латиница и кириллица). Апострофы вырезаются перед сравнением (см. dedupe).
    "maslahat", "konsalting", "dasturiy", "axborot tizim", "xizmat", "ishlab chiqish",
    "tadqiqot", "ilmiy", "iqtisodiy asos", "(tia)", "loyiha hujjat", "loyihalash", "ekspertiza",
    "baholash", "strategiya", "sertifikat", "tekshiruv", "xulosa", "metodika", "oqitish",
    "trening", "audit", "huquqiy", "yuridik", "tahlil",
    "маслаҳат", "хизмат", "ишлаб чиқиш", "тадқиқот", "илмий", "иқтисодий асос", "(тиа)",
    "лойиҳа ҳужжат", "лойиҳалаш", "экспертиза", "баҳолаш", "стратегия", "сертификат",
    "текширув", "хулоса", "методика", "ўқитиш", "ҳуқуқий", "юридик", "таҳлил", "техник топшириқ",
]

# ─────────────────────────── Профиль компании ───────────────────────────
COMPANY_PROFILE = """БОТ РАБОТАЕТ НА ТРИ ПРОФИЛЯ (Ташкент). Профиль — по документам компаний и заявкам (15.10.2026).

1) TopAdvisor (ООО BizAdvisor) — юридический и бизнес-консалтинг + цифровизация.
   • Право: корпоративное и коммерческое, M&A, due diligence, приватизация, антимонопольное,
     персональные данные, интеллектуальная собственность, юридические заключения; трудовое право,
     охрана труда, конвенции МОТ; социальная защита и соцуслуги; гендер.
   • Реформа регулирования: законопроекты, legal and regulatory framework, инвестклимат, ГЧП-рамка,
     институциональная реформа госорганов.
   • Бизнес-консалтинг: стратегии и дорожные карты, BPR/BPM, KPI, M&E, IVA, PIM, местные бюджеты,
     ТЭО и финмодели как бизнес-документ, оценка программ.
   • ЦИФРОВИЗАЦИЯ И ИС (профиль компании!): разработка (в т.ч. заказная), внедрение и сопровождение
     информационных систем, ERP/CRM, порталов, реестров и цифровых платформ — для госорганов, банков
     и компаний; e-gov, IFMIS/PFMIS, АСУ, интеграции, техподдержка ИС, ИТ-аудит, ТЗ и концепции систем.
2) UNISON CONSULT — энергетика и климат: энергоаудит, энергоэффективность, ISO 50001, ЭСКО;
   зелёное и климатическое финансирование (green lending, таксономия, GEFF, GCF); ESG, MRV, CBAM,
   декарбонизация, NDC; ВИЭ — политика, тарифы, ГЧП, инженер заказчика.
3) ГАЙРАТ ТАШМАТОВ — ИНДИВИДУАЛЬНЫЙ КОНСУЛЬТАНТ (PhD экономика, 15+ лет; экс-глава департамента
   стратпланирования Агентства стратегических реформ; проекты ВБ, ЕБРР, ЕС, GIZ). Ему — позиции
   individual consultant (национальные и международные), key/non-key expert в консорциумах,
   team leader, сотрудники PIU/ГРП (координатор, менеджер проекта, специалисты) по темам:
   • стратегическое планирование, RBM, M&E/MEL, KPI, реформа госуправления, региональное развитие,
     мастер-планы, оценка программ (evaluation), индексы благосостояния;
   • цифровое госуправление: концепции ИС и платформ, BPR As-Is/To-Be, бизнес-аналитик, service
     design, функциональные требования, ТЗ, интеграции, реестры, one-stop shop;
   • PFM: IFMIS/PFMIS, казначейство, исполнение бюджета, программное бюджетирование;
   • МСБ и деловая среда: программы поддержки МСБ, B-READY/Doing Business, инвестклимат, регуляторная
     реформа, инвестиционные платформы;
   • финансирование развития и агро: blended finance, agri/rural finance, farm credit, агростратегии;
   • энергоэффективность и ВИЭ (координация программ), ToR и закупочная документация (EU PRAG,
     Operations Manual), соцзащита и цифровизация соцуслуг.
   Только для позиций ЛИЧНО ему (audience = эксперт) — не подходят: программист/разработчик
   (full-stack, UX/UI, mobile), data analyst/статистик, бухгалтер/IPSAS/payroll, роли с обязательным
   дипломом юриста или инженера, административные и технические должности (ассистент, водитель).
   Эти ограничения НЕ относятся к фирменным тендерам: заказная разработка ИС — профиль TopAdvisor.
   Проектные позиции ООН и доноров (project manager/coordinator, specialist, NPSA, IC) — подходят.

ГЕОГРАФИЯ: Узбекистан; Центральная Азия (KAZ/KYR/TAJ/TUR) — одна страна или проект по ЦА;
для эксперта — также удалённые задания по Узбекистану. Глобальные извещения и другие регионы — НЕ наше.

НЕ НАШ ПРОФИЛЬ (даже если называется «консалтинг»): медицина, вакцины, клинические и
эпидемиологические исследования; ветеринария и агрономия как техника; строительство, СМР, EPC,
инженерное проектирование и технадзор; поставка товаров, оборудования и коробочного ПО/лицензий;
перевод и редактура; уборка, охрана, аренда, кейтеринг, логистика мероприятий, турагентства;
телемаркетинг, рекламные агентства, медиазакупки, видеопродакшн; преподавание в школах и вузах;
оплата участия сотрудников заказчика в курсах и конференциях. (Тренинги и capacity building по
нашим темам, которые проводит исполнитель, — наш профиль.)"""

# ─────────────────────────── Промпт фильтра ───────────────────────────
FILTER_PROMPT = """Ты — СТРОГИЙ фильтр релевантности для трёх профилей в Ташкенте: юрфирма TopAdvisor (право,
регуляторика, стратегии, KPI, BPR, M&E, PIM, разработка и внедрение ИС), UNISON (энергоаудит,
энергоэффективность, зелёное/климатическое финансирование, ESG) и Гайрат как индивидуальный
консультант (стратпланирование, M&E, цифровое госуправление и BPR, PFM/IFMIS, МСБ и B-READY, PIU).
География — только Узбекистан и Центральная Азия.

Оцени КАЖДЫЙ элемент 1–10: можно ли ЭТИМ компаниям продать здесь свою услугу.

ВЫСОКО (8–10) — услуга из профиля + Узбекистан/ЦА:
- «WB: Strengthening of Legal, Regulatory and Institutional Framework for Social Services, Uzbekistan» → 10
- «ADB: Climate Finance, Inclusive Transition and Sustainability Governance (Uzbekistan)» → 10
- «ADB: Strengthening Climate- and Gender-Responsive Public Investment Management» → 9
- «WB: Annual Performance Assessments (IVA), Livable and Productive Cities, Uzbekistan» → 9
- «EU: Agri-Food Development Strategy 2020-2030, second phase» → 8 (стратегия, не агрономия)
- «UNIDO: экономическая оценка эко-индустриальных парков в Узбекистане» → 9
- «Энергоаудит предприятий / закон об энергоэффективности / зелёная таксономия банков» → 9
- «Разработка и внедрение информационной системы / платформы / АСУ для госоргана», «техподдержка ИС» → 8
- Позиция индивидуального консультанта или PIU по темам Гайрата: «Individual Consultant on SME Support
  Programs», «Expert on B-READY», «Senior Business Analyst / Service Designer», «IFMIS integration
  concept», «Project Coordinator (PIU)», «M&E Specialist», «Strategic planning expert» → 9
- Принят указ/закон, меняющий регулирование бизнеса, труда, инвестиций, энергетики → 7–8

СРЕДНЕ (5–6) — пограничное: ESG-заверение (нужен аудитор-партнёр), обзоры образовательной или
медицинской ПОЛИТИКИ и их финансирования, ТЭО ВИЭ, зелёные здания, землепользование.

НИЗКО (1–3) — безжалостно отсекай, даже если в названии «consulting»/«консультант»:
- медицина, вакцины, ВИЧ/туберкулёз, клинические и эпидемиологические исследования → 1
  («Consulting Services to Support WHO in Enteric Vaccine R&D» → 1)
- агрономия/ветеринария/инженерия как техническая работа («Climate Smart Agriculture technology
  transfer», «Artificial Glacier System design») → 2
- поставка коробочного ПО, лицензий, оборудования; чистая разработка без госзаказчика (сайт кафе) → 2
- строительство, СМР, ремонт, поставка оборудования, мебели, авто, ПО «в коробке» → 1
- перевод, вычитка, уборка, охрана, аренда помещений, кейтеринг, организация семинаров,
  телемаркетинг, SEO/реклама, видеопродакшн, медицинские услуги → 1
- глобальное извещение или другой регион (MENA, Африка, ЛатАм, ЮВА, «global contract»,
  «multiple markets») без Узбекистана/ЦА → 1
- новости без конкретного проекта/закона/бюджета, мировые новости, криминал, спорт → 1–2

Тебе дан СПИСОК элементов (JSON). Верни ТОЛЬКО JSON-массив той же длины и порядка:
[{"i": <индекс>, "score": <1-10>, "reason": "<кратко>"}, ...]"""

# ─────────────────────────── Промпт анализа (для карточки сайта и Telegram) ───────────────────────────
ANALYSIS_PROMPT = """Ты — старший бизнес-аналитик двух консалтинговых компаний в Ташкенте (юрфирма TopAdvisor и
энергоконсалтинг UNISON). Проанализируй новость/тендер/НПА и дай практический разбор.
Будь строг к профилю: «консалтинг» в названии не делает тендер нашим.

ЯЗЫК: все текстовые поля — ВСЕГДА на русском (переводи суть, не копируй оригинал).
ФАКТЫ: используй только факты из текста источника; если данных нет — null.
Не придумывай суммы, сроки и названия.

{company_profile}

ШКАЛА relevance_score (для тендеров — строго по ней):
• 9–10: прямо наша услуга + Узбекистан. Примеры: правовая/регуляторная/институциональная рамка
  (соцуслуги, труд, инвестиции, ГЧП); стратегия, дорожная карта, KPI, M&E, IVA; управление
  госинвестициями (PIM), местные бюджеты, costing/financing analysis стратегии или программы;
  business engineering / BPR / реинжиниринг процессов и capacity building госоргана или компании;
  энергоаудит, энергоэффективность, зелёная таксономия, климатическое финансирование и климатическое
  управление, MRV, CBAM, ESG-стратегия; юридическое сопровождение, due diligence, IP; разработка,
  внедрение, интеграция и сопровождение информационных систем и цифровых платформ госорганов;
  позиции индивидуального консультанта / key expert / PIU по темам Гайрата (см. профиль 3).
• 7–8: то же, но Центральная Азия (KAZ/KYR/TAJ/TUR) или многострановой проект ЦА; либо наша услуга
  как часть более широкого задания (ТЭО как бизнес-документ, оценка программы, налоговая/фискальная
  политика, гендерные планы и методики, анализ рынка труда и данных по охране труда, HR- и
  институциональные оценки организаций).
• 5–6 (profile_match = «пограничный»): ESG-заверение (нужен аудитор), обзоры политики в образовании
  или здравоохранении и их финансирования, ТЭО ВИЭ как инженерия, зелёные здания, биоразнообразие,
  информационные кампании.
• 1–3 (profile_match = «нет»): медицина и вакцины, агротехника и ветеринария, инженерия и стройка,
  поставки товаров и лицензий, перевод/вычитка, мероприятия и логистика, SEO/реклама/коммуникации,
  глобальные извещения и другие регионы; для индивидуальных позиций — роли вне профиля 3.
«пограничный» — ТОЛЬКО для перечисленного в 5–6; если услуга из 9–10 или 7–8 — ставь право/бизнес/
энергетика_климат, даже если отрасль чужая (стратегия в агро или соцсфере — это «бизнес»).
geo — где выполняется работа: если в тексте или заголовке есть страна ЦА ([UN·UZB] = Узбекистан),
это она, а не «глобальный».

ИСТОЧНИК: {source} ({category})
Заголовок: {title}
URL: {url}
Текст: {text}

Верни ТОЛЬКО JSON (без markdown, без пояснений):
{{
  "title_ru": "<чёткий короткий заголовок НА РУССКОМ, 5–10 слов>",
  "summary_ru": "<2–3 предложения: ЧТО закупается/происходит, КТО заказчик, СКОЛЬКО, срок — только факты>",
  "site_brief": "<развёрнутый разбор для сайта, 4–6 предложений: контекст, что именно потребуется исполнителю, на что обратить внимание>",
  "relevance_score": <1-10: можно ли ЭТИМ компаниям продать здесь услугу из их профиля>,
  "profile_match": "<право|бизнес|ИТ_цифровизация|энергетика_климат|пограничный|нет> — по СУТИ работы, а не по слову «consulting»: вакцины, медицина, стройка, агротехника, перевод, мероприятия = нет>",
  "audience": "<компания|эксперт|оба> — «эксперт»: набор ИНДИВИДУАЛЬНОГО консультанта, key expert, сотрудника PIU/ГРП, ростер экспертов; «компания»: отбор фирм (QCBS/CQS/RFP/EOI фирм), госзакупка услуг; «оба» — если подойдёт и фирме, и эксперту>",
  "profile_reason": "<одно предложение БЕЗ названий компаний и имён людей: какая работа здесь нужна и к какому направлению она относится (право, бизнес-консалтинг, ИТ и цифровизация, энергетика и климат), или почему не подходит>",
  "geo": "<узбекистан|центральная_азия|глобальный|другой_регион> — где выполняется работа>",
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


# ─────────────────────────── Карта доноров (03.09.2026) ───────────────────────────
# Подключено: World Bank (API), UNGM = вся система ООН (ПРООН, ЮНИСЕФ, МОТ, ФАО, IOM, WFP,
#   ЮНЕСКО, UN Women, UNOPS, ВОЗ… — headless по 5 странам ЦА), UNDP (прямой сайт),
#   IsDB (loc=UZ), EBRD ECEPP (headless), AIIB (RSS), EU TED (API), TenderWeek/etender/xt-xarid.
# Закрыто анти-ботом (403 даже для браузера) — только через e-mail-алерты аккаунта:
#   UNIDO (закупки идут ТАКЖЕ через UNGM → покрыто), ADB CMS/CSRN (консалтинг ADB через
#   CSRN требует логина; проекты по УЗ — через ADB e-mail alerts), DevelopmentAid, Devex.
# Не имеют открытого потока по УЗ: GIZ (только DE-портал без фильтра страны), KfW, AFD, EIB.
DONOR_MAP_NOTE = "см. комментарий выше"


# ─────────────────────────── Разбор нормативного акта (15.10.2026) ───────────────────────────
ACT_SPHERES = ["налоги", "труд и занятость", "социальная защита", "инвестиции и ГЧП", "банки и финансы",
               "энергетика", "экология и климат", "цифровизация и ИТ", "госзакупки", "госуправление",
               "корпоративное право", "интеллектуальная собственность", "торговля и таможня",
               "сельское хозяйство", "строительство и недвижимость", "здравоохранение", "образование",
               "транспорт", "судебная система", "прочее"]

ACT_REVIEW_PROMPT = """Ты — старший юрист юридической фирмы в Ташкенте. Перед тобой нормативный акт
Узбекистана (полный текст или скан; язык — узбекский или русский). Подготовь разбор НА РУССКОМ для
двух аудиторий: юристов и консультантов фирмы и их клиентов-бизнеса.

{company_profile}

Правила: только факты из текста акта; если чего-то в тексте нет — пустой список или пустая строка,
ничего не придумывай. Пиши простым деловым языком, без канцелярита, конкретно (кто, что, к какому сроку).
importance: «высокая» — меняет правила для бизнеса/инвесторов/работодателей, вводит обязанности,
льготы, новые процедуры или крупные госпрограммы с закупками; «средняя» — отраслевые изменения;
«низкая» — кадровые, организационные, узкие технические акты.
opportunities — что конкретно могут предложить: TopAdvisor (право, регуляторика, стратегии, BPR,
KPI, ИС и цифровизация), UNISON (энергоэффективность, климат, зелёное финансирование, ESG),
Гайрат как индивидуальный консультант, или что делать бизнесу. Без общих слов. Адресат — только в
поле «for»; в тексте «what» НЕ называй компании и людей (текст публикуется в Telegram-канале).
expected_procurements — какие разработки, исследования, информационные системы, консультанты,
программы акт поручает создать/привлечь (это будущие тендеры), с ответственным органом и сроком.

Реквизиты из RSS (для сверки): {meta}"""

ACT_REVIEW_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["title_ru", "act_type", "number", "adopted", "effective", "importance", "spheres",
                 "essence", "key_changes", "who_affected", "business_impact", "obligations",
                 "opportunities", "expected_procurements", "risks"],
    "properties": {
        "title_ru": {"type": "string", "description": "Краткое название на русском, до 15 слов, без «О мерах по»"},
        "act_type": {"type": "string", "description": "Закон / Указ Президента / Постановление Президента / Постановление Кабинета Министров / Ведомственный акт / Иное"},
        "number": {"type": "string"}, "adopted": {"type": "string", "description": "ГГГГ-ММ-ДД или пусто"},
        "effective": {"type": "string", "description": "ГГГГ-ММ-ДД или пусто"},
        "importance": {"type": "string", "enum": ["высокая", "средняя", "низкая"]},
        "spheres": {"type": "array", "items": {"type": "string", "enum": ACT_SPHERES}},
        "essence": {"type": "string", "description": "Суть в 2–3 предложениях простым языком"},
        "key_changes": {"type": "array", "items": {"type": "string"}, "description": "3–7 конкретных изменений"},
        "who_affected": {"type": "array", "items": {"type": "string"}},
        "business_impact": {"type": "string", "description": "Что это значит для бизнеса и инвесторов, 2–4 предложения"},
        "obligations": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                        "required": ["who", "what", "deadline"],
                        "properties": {"who": {"type": "string"}, "what": {"type": "string"}, "deadline": {"type": "string"}}}},
        "opportunities": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                          "required": ["for", "what"],
                          "properties": {"for": {"type": "string", "enum": ["TopAdvisor", "UNISON", "Гайрат", "бизнес"]},
                                         "what": {"type": "string"}}}},
        "expected_procurements": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
    },
}


# ─────────────────────────── Недельный регуляторный обзор (15.10.2026) ───────────────────────────
WEEKLY_PROMPT = """Ты — управляющий партнёр юридической фирмы в Ташкенте. Ниже — готовые разборы
нормативных актов Узбекистана, принятых за неделю {period}. Подготовь НЕДЕЛЬНЫЙ РЕГУЛЯТОРНЫЙ ОБЗОР
для руководителей компаний и для команды фирмы: что главное, что делать, где деньги и работа.

{company_profile}

Правила: только факты из разборов; реквизиты актов — как в данных; деловой язык без воды;
группируй по сферам, не перечисляй подряд; акты низкой важности упоминай одной строкой или не упоминай.

РАЗБОРЫ АКТОВ (JSON):
{acts}"""

WEEKLY_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["title", "lead", "top_acts", "sections", "for_business", "opportunities", "pipeline", "calendar"],
    "properties": {
        "title": {"type": "string", "description": "Заголовок с периодом, ёмкий, без слова «дайджест»"},
        "lead": {"type": "string", "description": "Главное за неделю, 3–4 предложения"},
        "top_acts": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                     "required": ["act", "title", "why", "action"],
                     "properties": {"act": {"type": "string"}, "title": {"type": "string"},
                                    "why": {"type": "string"}, "action": {"type": "string"}}},
                     "description": "3–5 самых важных актов недели"},
        "sections": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                     "required": ["sphere", "body", "acts"],
                     "properties": {"sphere": {"type": "string"}, "body": {"type": "string"},
                                    "acts": {"type": "array", "items": {"type": "string"}}}}},
        "for_business": {"type": "array", "items": {"type": "string"},
                         "description": "Чек-лист: что сделать компаниям, 3–6 пунктов с адресатом"},
        "opportunities": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                          "required": ["for", "what", "act"],
                          "properties": {"for": {"type": "string", "enum": ["TopAdvisor", "UNISON", "Гайрат"]},
                                         "what": {"type": "string"}, "act": {"type": "string"}}}},
        "pipeline": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                     "required": ["what", "who", "when", "act"],
                     "properties": {"what": {"type": "string"}, "who": {"type": "string"},
                                    "when": {"type": "string"}, "act": {"type": "string"}}},
                     "description": "Ожидаемые закупки и проекты: разработки, ИС, исследования, консультанты"},
        "calendar": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                     "required": ["date", "what", "act"],
                     "properties": {"date": {"type": "string"}, "what": {"type": "string"},
                                    "act": {"type": "string"}}},
                     "description": "Вступление в силу и сроки исполнения на ближайшие недели"},
    },
}
