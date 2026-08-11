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

    # Пол для международных донорских тендеров — релевантны по определению.
    for it in items:
        if it["category"] == config.CAT_INTL:
            it["score"] = max(it.get("score", 0), 7)


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
        if not isinstance(data.get("docs_checklist"), list):
            data["docs_checklist"] = []
        return data
    except Exception as e:
        log.warning("LLM-анализ FAIL: %s", e)
        return _fallback(item)
