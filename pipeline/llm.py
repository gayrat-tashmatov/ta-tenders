"""
LLM-пайплайн: дешёвый фильтр (Haiku, батч) → анализ карточки (для сайта и Telegram).

Без ANTHROPIC_API_KEY деградирует мягко: эвристический скоринг + заглушка анализа
(dry-режим, ничего не стоит). ANALYZE_MAX ограничивает число анализов за запуск.
"""

import json
import re
import logging

import config

log = logging.getLogger("llm")

_client = None


def _anthropic():
    global _client
    if _client is None:
        from anthropic import Anthropic
        _client = Anthropic(api_key=config.ANTHROPIC_KEY)
    return _client


def _resp_text(resp) -> str:
    parts = []
    for b in getattr(resp, "content", []) or []:
        if getattr(b, "type", None) == "text":
            parts.append(getattr(b, "text", ""))
    return "\n".join(p for p in parts if p).strip()


def _extract_json(text: str):
    """Первое верхнеуровневое JSON-значение (объект или массив) из ответа модели."""
    text = (text or "").strip()
    start = next((k for k, ch in enumerate(text) if ch in "[{"), None)
    if start is None:
        return None
    depth, in_str, esc = 0, False, False
    for k in range(start, len(text)):
        c = text[k]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:k + 1])
                except Exception:
                    return None
    return None


# ─────────────────────────── Фильтр ───────────────────────────
def _heuristic_score(item: dict) -> int:
    return {config.CAT_INTL: 8, config.CAT_UZTEND: 6, config.CAT_JOB: 6,
            config.CAT_LAW: 6, config.CAT_NEWS: 4}.get(item.get("category"), 4)


def filter_batch(items: list, chunk: int = 15) -> None:
    """Проставляет item['score'] и item['reason'] (in place)."""
    if not config.ANTHROPIC_KEY:
        for it in items:
            it["score"] = _heuristic_score(it)
            it["reason"] = "эвристика (без ключа)"
        return

    for start in range(0, len(items), chunk):
        batch = items[start:start + chunk]
        payload = [{"i": k, "category": it["category"], "source": it["origin"],
                    "title": it["title"], "summary": it["summary"][:400]}
                   for k, it in enumerate(batch)]
        try:
            resp = _anthropic().messages.create(
                model=config.MODEL_FILTER, max_tokens=2048,
                messages=[{"role": "user",
                           "content": config.FILTER_PROMPT + "\n\nЭЛЕМЕНТЫ:\n" +
                           json.dumps(payload, ensure_ascii=False)}])
            arr = _extract_json(_resp_text(resp))
            if not isinstance(arr, list):
                arr = []
            by_i = {d.get("i"): d for d in arr if isinstance(d, dict)}
            for k, it in enumerate(batch):
                d = by_i.get(k, {})
                try:
                    it["score"] = int(d.get("score", _heuristic_score(it)))
                except (TypeError, ValueError):
                    it["score"] = _heuristic_score(it)
                it["reason"] = d.get("reason", "")
        except Exception as e:
            log.warning("Haiku-фильтр FAIL (батч %d): %s", start, e)
            for it in batch:
                it["score"] = _heuristic_score(it)
                it["reason"] = "fallback"

    # Пола «международный = 7» больше нет (до 15.10 он отправлял в канал ВСЕ извещения UNGM,
    # в т.ч. вакцины ВОЗ и уборку): тендеры и так все идут на разбор, решает разбор.


# ─────────────────────────── Анализ ───────────────────────────
def _fallback(item: dict) -> dict:
    title = re.sub(r"^\[[^\]]+\]\s*", "", item.get("title", "")).strip()
    return {"relevance_score": item.get("score", 6),
            "title_ru": title[:120], "summary_ru": title[:300],
            "site_brief": None, "consulting_recommendation": None,
            "urgency": "средняя", "npa_ref": None, "eligibility": None,
            "docs_checklist": [],
            "opportunity_type": "тендер" if item["category"] in
            (config.CAT_INTL, config.CAT_UZTEND) else "нет",
            "target_entity": None, "budget_info": None, "deadline_info": None}


def analyze(item: dict) -> dict:
    if not config.ANTHROPIC_KEY:
        return _fallback(item)
    try:
        prompt = config.ANALYSIS_PROMPT.format(
            company_profile=config.COMPANY_PROFILE, source=item["origin"],
            category=item["category"], title=item["title"], url=item["url"],
            text=item["full_text"][:5000])
        resp = _anthropic().messages.create(
            model=config.MODEL_ANALYZE, max_tokens=4096,
            messages=[{"role": "user", "content": prompt}])
        data = _extract_json(_resp_text(resp))
        if not isinstance(data, dict):
            raise ValueError("ожидали JSON-объект анализа")
        try:
            data["relevance_score"] = int(data.get("relevance_score"))
        except (TypeError, ValueError):
            data["relevance_score"] = int(item.get("score", 6))
        for key in ("docs_checklist", "legal_aspects", "action_items"):
            if not isinstance(data.get(key), list):
                data[key] = []
        return data
    except Exception as e:
        log.warning("LLM-анализ FAIL: %s", e)
        return _fallback(item)


# ─────────────────────────── Разбор акта (Opus 5.5, полный текст или PDF-скан) ───────────────────────────
_IMPORTANCE_SCORE = {"высокая": 8, "средняя": 6, "низкая": 4}


def review_act(item: dict, kind: str | None, payload) -> dict | None:
    """Структурированный разбор акта. kind: 'text' | 'pdf' | None (тогда — по реквизитам из RSS).
    JSON гарантирован схемой (output_config.format). Отказ модели → None."""
    if not config.ANTHROPIC_KEY:
        return None
    import base64
    meta = item.get("meta") or {}
    prompt = config.ACT_REVIEW_PROMPT.format(
        company_profile=config.COMPANY_PROFILE,
        meta=f"{item.get('title','')} | {meta.get('act_info') or item.get('summary','')[:300]} | {item.get('url','')}")
    content = []
    if kind == "pdf":
        content.append({"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                                       "data": base64.b64encode(payload).decode()}})
        content.append({"type": "text", "text": prompt})
    elif kind == "text":
        content.append({"type": "text", "text": prompt + "\n\nТЕКСТ АКТА:\n" + str(payload)[:40000]})
    else:
        content.append({"type": "text", "text": prompt + "\n\nПолного текста нет — разбери по реквизитам, "
                        "importance не выше «средняя», списки оставь пустыми, если данных нет."})
    try:
        resp = _anthropic().beta.messages.create(
            model=config.MODEL_ACT, max_tokens=16000,
            output_config={"effort": "medium",
                           "format": {"type": "json_schema", "schema": config.ACT_REVIEW_SCHEMA}},
            betas=["server-side-fallback-2026-07-01"],
            extra_body={"fallbacks": "default"},     # отказ классификатора → модель-замена на сервере
            messages=[{"role": "user", "content": content}])
        if resp.stop_reason == "refusal":
            log.warning("Разбор акта: отказ модели (%s)", getattr(resp.stop_details, "category", None))
            return None
        data = json.loads(next(b.text for b in resp.content if b.type == "text"))
        data["source_kind"] = kind or "meta"
        return data
    except Exception as e:
        log.warning("Разбор акта FAIL %s: %s", item.get("uid"), e)
        return None


def act_to_analysis(review: dict) -> dict:
    """Разбор акта → поля карточки (совместимо с остальным сайтом) + сам разбор в analysis['act']."""
    imp = review.get("importance") or "средняя"
    opp = "; ".join(f"{o['for']}: {o['what']}" for o in review.get("opportunities", [])[:3])
    return {"title_ru": review.get("title_ru"), "summary_ru": review.get("essence"),
            "site_brief": review.get("business_impact"), "relevance_score": _IMPORTANCE_SCORE.get(imp, 6),
            "opportunity_type": "нпа", "npa_ref": review.get("number") or None,
            "consulting_recommendation": opp or None,
            "legal_aspects": review.get("key_changes", [])[:5],
            "action_items": [f"{o['who']}: {o['what']}" + (f" — до {o['deadline']}" if o.get("deadline") else "")
                             for o in review.get("obligations", [])[:4]],
            "urgency": {"высокая": "высокая", "средняя": "средняя"}.get(imp, "низкая"),
            "deadline_info": None, "target_entity": None, "budget_info": None,
            "act": review}
