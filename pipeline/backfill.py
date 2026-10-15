"""Разовый догон (15.10.2026): разметка профиля для открытых тендеров и разборы актов.
python backfill.py profile [N] | acts [N]"""
import json
import sys
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import config
import dedupe
import llm
import sources
from store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("backfill")

PROFILE_PROMPT = """Разметь каждую позицию (тендер/вакансию) по профилю. Профиль:
{profile}

Для КАЖДОГО элемента верни: i; profile_match (право|бизнес|ИТ_цифровизация|энергетика_климат|пограничный|нет —
по сути работы, а не по слову «consulting»); profile_reason (одно предложение по-русски: какая наша услуга
здесь нужна или почему не наше); audience (компания|эксперт|оба — «эксперт» для индивидуальных консультантов,
key expert, позиций PIU); geo (узбекистан|центральная_азия|глобальный|другой_регион); relevance_score 1–10
по шкале: 9–10 прямо наше + Узбекистан, 7–8 наше в ЦА или как часть задания, 5–6 пограничное, 1–3 не наше.
Верни ТОЛЬКО JSON-массив той же длины.

ЭЛЕМЕНТЫ:
{items}"""


def backfill_profile(limit: int):
    st = Store()
    rows = st.db.execute(
        """SELECT * FROM items WHERE category IN (?,?,?)
           AND (analysis IS NULL OR json_extract(analysis,'$.profile_match') IS NULL)
           AND first_seen >= date('now','-75 days')
           AND (json_extract(meta,'$.deadline') IS NULL OR json_extract(meta,'$.deadline') NOT LIKE '20%'
                OR substr(json_extract(meta,'$.deadline'),1,10) >= date('now'))
           ORDER BY first_seen DESC LIMIT ?""",
        (config.CAT_INTL, config.CAT_UZTEND, config.CAT_JOB, limit)).fetchall()
    log.info("профиль: к разметке %d", len(rows))
    batches = [rows[k:k + 12] for k in range(0, len(rows), 12)]

    def run(batch):
        payload = [{"i": k, "title": r["title"], "summary": (r["summary"] or "")[:350], "source": r["origin"]}
                   for k, r in enumerate(batch)]
        try:
            resp = llm._anthropic().messages.create(
                model=config.MODEL_FILTER, max_tokens=4096,
                messages=[{"role": "user", "content": PROFILE_PROMPT.format(
                    profile=config.COMPANY_PROFILE, items=json.dumps(payload, ensure_ascii=False))}])
            arr = llm._extract_json(llm._resp_text(resp)) or []
            return batch, {d.get("i"): d for d in arr if isinstance(d, dict)}
        except Exception as e:
            log.warning("батч FAIL: %s", e)
            return batch, {}

    done = 0
    with ThreadPoolExecutor(4) as ex:
        for batch, by in ex.map(run, batches):
            for k, r in enumerate(batch):
                d = by.get(k)
                if not d:
                    continue
                a = json.loads(r["analysis"] or "{}") if r["analysis"] else {}
                for f in ("profile_match", "profile_reason", "audience", "geo"):
                    if d.get(f):
                        a[f] = d[f]
                try:
                    sc = int(d.get("relevance_score"))
                except (TypeError, ValueError):
                    sc = r["score"] or 5
                pm, geo = str(a.get("profile_match", "")).lower(), str(a.get("geo", "")).lower()
                if pm == "нет" or geo in ("глобальный", "другой_регион"):
                    sc = min(sc, 3)
                elif pm == "пограничный":
                    sc = min(sc, 6)
                a.setdefault("relevance_score", sc)
                st.db.execute("UPDATE items SET analysis=?, score=? WHERE id=?",
                              (json.dumps(a, ensure_ascii=False), sc, r["id"]))
                done += 1
            st.db.commit()
    log.info("профиль: размечено %d", done)


def backfill_acts(limit: int):
    st = Store()
    allrows = st.db.execute(
        """SELECT * FROM items WHERE category=? AND first_seen >= date('now','-21 days')
           AND (analysis IS NULL OR json_extract(analysis,'$.act') IS NULL)
           ORDER BY first_seen DESC""", (config.CAT_LAW,)).fetchall()
    rows = []
    for r in allrows:
        it = dict(r)
        it["meta"] = json.loads(r["meta"] or "{}")
        it["npa_refs"] = json.loads(r["npa_refs"] or "[]")
        if dedupe.is_major_act(it) or (r["score"] or 0) >= config.ACT_MIN_FILTER_SCORE:
            rows.append(r)
    rows = rows[:limit]
    log.info("акты: к разбору %d", len(rows))

    def run(r):
        it = dict(r)
        it["meta"] = json.loads(r["meta"] or "{}")
        kind, payload = sources.fetch_act_text(it["url"])
        return r, kind, llm.review_act(it, kind, payload)

    done = 0
    with ThreadPoolExecutor(4) as ex:
        for r, kind, rv in ex.map(run, rows):
            if not rv:
                continue
            a = llm.act_to_analysis(rv)
            st.db.execute("UPDATE items SET analysis=?, score=? WHERE id=?",
                          (json.dumps(a, ensure_ascii=False), a["relevance_score"], r["id"]))
            st.db.commit()
            done += 1
            log.info("акт [%s/%s] %s", rv.get("importance"), kind or "реквизиты", rv.get("title_ru", "")[:70])
    log.info("акты: разобрано %d", done)


if __name__ == "__main__":
    what = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    {"profile": backfill_profile, "acts": backfill_acts}[what](n)
