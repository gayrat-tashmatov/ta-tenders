"""
Почтовые рассылки площадок, закрытых логином и защитой от ботов (DevelopmentAid и др.).

Схема: на площадке настроен сохранённый поиск (Узбекистан + ЦА, тендеры и гранты) с
ежедневной рассылкой на ОТДЕЛЬНЫЙ ящик. Пайплайн читает этот ящик по IMAP паролем
приложения из GitHub Secrets (ALERTS_IMAP_USER / ALERTS_IMAP_PASS) — пароль от самой
площадки не нужен никому, вход на площадку не автоматизируется.

Ящик не меняется (письма открываются только на чтение, флаги не ставим): повтор
отсекает наш вечный seen по uid. Формат писем у площадок разный и меняется — позиции
извлекает Haiku из текста письма (название, донор, страна, срок, ссылка).
"""
import os
import re
import json
import email
import hashlib
import imaplib
import logging
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header

import config
from sources import _mk, strip_html

log = logging.getLogger("mail_alerts")

IMAP_HOST = os.getenv("ALERTS_IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.getenv("ALERTS_IMAP_USER", "")
IMAP_PASS = os.getenv("ALERTS_IMAP_PASS", "")
SENDERS = [s.strip() for s in os.getenv(
    "ALERTS_SENDERS", "developmentaid.org,mangofetch.com,ungm.org,adb.org,devex.com").split(",") if s.strip()]
DAYS_BACK = int(os.getenv("ALERTS_DAYS_BACK", "4"))

EXTRACT_PROMPT = """Это письмо-рассылка площадки тендеров/грантов. Извлеки из него ВСЕ позиции
(тендеры, гранты, вакансии экспертов). Для каждой верни поля строго из текста письма:
title — название как в письме; donor — источник финансирования/донор/заказчик (World Bank,
ADB, EU, USAID, GIZ, UNDP…) или null; country — страна/регион из письма или null;
deadline — срок подачи в формате ГГГГ-ММ-ДД, если указан, иначе null; url — ссылка на
позицию из письма или null; kind — "tender" | "grant" | "job".
Не придумывай. Рекламные блоки, ссылки отписки и меню — не позиции.
Верни ТОЛЬКО JSON-массив: [{{"title":..., "donor":..., "country":..., "deadline":..., "url":..., "kind":...}}]

ПИСЬМО (отправитель: {sender}, тема: {subject}):
{body}"""


def _decode(v) -> str:
    try:
        return str(make_header(decode_header(v or "")))
    except Exception:
        return v or ""


def _body(msg) -> str:
    """Текст письма: ссылки сохраняем рядом с текстом (в рассылках они — главное)."""
    html, plain = "", ""
    for part in msg.walk():
        ctype = part.get_content_type()
        if part.get_content_maintype() == "multipart":
            continue
        try:
            payload = part.get_payload(decode=True) or b""
            text = payload.decode(part.get_content_charset() or "utf-8", "ignore")
        except Exception:
            continue
        if ctype == "text/html":
            html += text
        elif ctype == "text/plain":
            plain += text
    if html:
        html = re.sub(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                      lambda m: f" {strip_html(m.group(2))} [ссылка: {m.group(1)}] ", html, flags=re.S | re.I)
        return strip_html(html)
    return plain


def _uid_for(entry: dict, sender: str) -> str:
    url = entry.get("url") or ""
    m = re.search(r"developmentaid\.org/(?:tenders|grants|jobs)/view/(\d+)", url)
    if m:
        return f"da:{m.group(1)}"
    m = re.search(r"mangofetch\.com/tenders/([0-9a-f-]{36})", url)
    if m:
        return f"mf:{m.group(1)}"
    key = url or f"{sender}|{entry.get('title','')}"
    return "mail:" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def fetch_mail_alerts() -> list:
    if not (IMAP_USER and IMAP_PASS):
        log.info("Почтовые рассылки: ящик не настроен (ALERTS_IMAP_USER/PASS) — пропуск")
        return []
    if not config.ANTHROPIC_KEY:
        log.info("Почтовые рассылки: нет ключа Anthropic для разбора писем — пропуск")
        return []
    import llm
    items = []
    try:
        box = imaplib.IMAP4_SSL(IMAP_HOST)
        box.login(IMAP_USER, IMAP_PASS)
        box.select("INBOX", readonly=True)                 # только чтение, флаги не трогаем
        since = (datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).strftime("%d-%b-%Y")
        ids = set()
        for snd in SENDERS:
            typ, data = box.search(None, f'(SINCE {since} FROM "{snd}")')
            if typ == "OK" and data and data[0]:
                ids.update(data[0].split())
        log.info("Почтовые рассылки: писем за %d дн — %d", DAYS_BACK, len(ids))
        for mid in sorted(ids):
            typ, data = box.fetch(mid, "(BODY.PEEK[])")
            if typ != "OK" or not data or not isinstance(data[0], tuple):
                continue
            msg = email.message_from_bytes(data[0][1])
            sender = _decode(msg.get("From"))
            subject = _decode(msg.get("Subject"))
            body = _body(msg)[:14000]
            try:
                resp = llm._anthropic().messages.create(
                    model=config.MODEL_FILTER, max_tokens=4096,
                    messages=[{"role": "user", "content": EXTRACT_PROMPT.format(
                        sender=sender, subject=subject, body=body)}])
                arr = llm._extract_json(llm._resp_text(resp))
            except Exception as e:
                log.warning("Почтовые рассылки: разбор письма «%s» FAIL: %s", subject[:60], e)
                continue
            if not isinstance(arr, list):
                continue
            platform = next((s for s in SENDERS if s in sender.lower()), "e-mail")
            for ent in arr:
                if not isinstance(ent, dict) or not ent.get("title"):
                    continue
                title = str(ent["title"]).strip()
                donor = (ent.get("donor") or "").strip() or None
                country = (ent.get("country") or "").strip() or None
                deadline = (ent.get("deadline") or "") or None
                kind = ent.get("kind") or "tender"
                tag = {"grant": "Грант", "job": "Эксперт"}.get(kind, "Тендер")
                bits = [f"{tag}. Площадка: {platform}."]
                if donor:
                    bits.append(f"Донор (источник финансирования): {donor}.")
                if country:
                    bits.append(f"Страна: {country}.")
                if deadline:
                    bits.append(f"Срок: {deadline}.")
                items.append(_mk(
                    f"{platform} (рассылка)", config.CAT_JOB if kind == "job" else config.CAT_INTL,
                    platform, f"[{platform.split('.')[0][:12]}] {title[:260]}",
                    ent.get("url") or "", None,
                    summary=" ".join(bits), full_text=f"{title}. " + " ".join(bits),
                    uid=_uid_for(ent, platform),
                    meta={"donor": donor, "country": country, "deadline": deadline,
                          "kind": kind, "cross_source": True, "via_mail": subject[:120]}))
        box.logout()
    except Exception as e:
        log.warning("Почтовые рассылки FAIL: %s", e)
    log.info("Почтовые рассылки: позиций %d", len(items))
    return items
