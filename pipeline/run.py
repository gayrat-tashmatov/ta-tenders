#!/usr/bin/env python3
"""
TA Tenders — оркестратор пайплайна.

  python3 run.py --test      проверка связи (источники, Telegram, ключи)
  python3 run.py --collect   только сбор + счётчики (без LLM и Telegram)
  python3 run.py --run       полный цикл: сбор → дедуп → LLM → сохранение → экспорт → Telegram
  python3 run.py --run --no-telegram   то же, но без отправки (для локальной отладки)
  python3 run.py --export    только перегенерировать web/data из базы

Порядок дедупа в --run:
  свежесть → вечный seen (uid/URL/контент) → реестр НПА (упоминание вместо дубля)
  → семантический дедуп против истории 14 дней → дубли внутри запуска.
"""

import sys
import logging
import argparse
import traceback

import requests

import config
import sources
import dedupe
import llm
import notify
import export
import insights
from store import Store


def setup_logging():
    config.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)])
    return logging.getLogger("run")


log = logging.getLogger("run")


def _ping(fail=False):
    if not config.HEALTHCHECK_URL:
        return
    try:
        requests.get(config.HEALTHCHECK_URL + ("/fail" if fail else ""), timeout=10)
    except Exception:
        pass


def _alert(msg: str):
    try:
        notify._send(f"🚨 <b>TA Tenders — сбой</b>\n<pre>{notify.esc(msg[:500])}</pre>")
    except Exception:
        pass


# ─────────────────────────── Полный цикл ───────────────────────────
def run(send_telegram: bool = True):
    store = Store()
    try:
        raw = sources.collect_all()
        if not raw:
            log.error("Сбор вернул 0 элементов — вероятная поломка источников")
            _alert("Сбор вернул 0 элементов")
            _ping(fail=True)
            return

        store.record_health(sources.LAST_COLLECT_STATS)
        history = store.recent_tokens()
        fresh, mentions_only, goods_skipped, offregion_skipped = [], 0, 0, 0
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=config.MAX_AGE_DAYS)

        for it in raw:
            pub = it.get("published")
            if pub is not None:
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                if it["category"] == config.CAT_NEWS and pub < cutoff:
                    continue

            it["npa_refs"] = dedupe.extract_npa_refs(it.get("title"), it.get("full_text"))

            # Чужой регион (Африка/ЛатАм/ЮВА без упоминания ЦА) — не наш рынок.
            if dedupe.is_off_region(it):
                store.mark_seen(it)
                offregion_skipped += 1
                continue
            # Закупки товаров/оборудования — не наш профиль: отсекаем на входе.
            if dedupe.is_goods_procurement(it):
                store.mark_seen(it)
                goods_skipped += 1
                continue

            # Повтор той же записи (тот же uid/URL/текст) — просто пропуск.
            if store.is_seen(it):
                continue

            # НОВАЯ публикация про уже известный акт → упоминание к карточке,
            # не отдельная запись (это и убирает повторы НПА). Только для НОВОСТЕЙ:
            # сам акт (lex.uz) — всегда своя карточка.
            if (it["category"] == config.CAT_NEWS and it["npa_refs"]
                    and store.npa_lookup(it["npa_refs"])):
                store.npa_add_mention(it["npa_refs"], it)
                store.mark_seen(it)
                mentions_only += 1
                continue
            # Семантический дедуп — ТОЛЬКО для новостей (одна тема из разных СМИ).
            # Тендеры/НПА/вакансии дедупятся строго по uid/URL: у госзакупок
            # шаблонные названия («Консультационные услуги»), и по словам они
            # ложно склеивались — так терялись реальные лоты (баг до 18.08).
            if it["category"] == config.CAT_NEWS and dedupe.is_near_dup(it, history):
                store.mark_seen(it)
                continue
            fresh.append(it)

        log.info("После свежести+дедупа: %d из %d (+%d упоминаний НПА, %d товарных, %d чужой регион)",
                 len(fresh), len(raw), mentions_only, goods_skipped, offregion_skipped)

        if not fresh:
            if send_telegram:
                notify._send("🟢 <b>TA Tenders</b>\nНовых материалов нет.")
            export.export_all(store)
            _ping()
            return

        llm.filter_batch(fresh)
        # Лоты, прошедшие словарь консалтинга/ИТ (headless), гарантированно идут
        # на LLM-разбор: он и решит, отправлять ли (relevance_score ≥ 7).
        for it in fresh:
            if it.get("meta", {}).get("kw_match") and it["category"] == config.CAT_UZTEND:
                it["score"] = max(it.get("score", 0), config.MIN_SCORE_FOR_DEEP)
        before = len(fresh)
        news_part = [it for it in fresh if it["category"] == config.CAT_NEWS]
        other_part = [it for it in fresh if it["category"] != config.CAT_NEWS]
        fresh = other_part + dedupe.dedup_within_run(news_part)
        log.info("После дедупа новостей внутри запуска: %d из %d", len(fresh), before)

        processed, analyzed = [], 0
        # Тендеры/НПА/вакансии — на сайт ВСЕ (оценка влияет только на Telegram и
        # порядок). Разбор LLM получают релевантные (score ≥ MIN_SCORE_FOR_DEEP)
        # и, отдельно, все тендеры в пределах бюджета анализов.
        for it in sorted(fresh, key=lambda x: -x.get("score", 0)):
            score = it.get("score", 0)
            is_tender = it["category"] in (config.CAT_INTL, config.CAT_UZTEND, config.CAT_JOB)
            want_deep = (score >= config.MIN_SCORE_FOR_DEEP or is_tender) \
                and analyzed < config.ANALYZE_MAX
            if not want_deep:
                store.save_item(it, score, None, it["npa_refs"], notified=False)
                if it["category"] == config.CAT_LAW and it["npa_refs"]:
                    store.npa_register(it["npa_refs"], it)
                store.mark_seen(it)
                continue

            # Полный текст страницы для глубокого анализа (news, UNGM, UNDP, uzjobs):
            # снippet'а мало — дотягиваем статью/извещение, как делал v4.
            if len(it.get("full_text") or "") < 700:
                page_text = sources.fetch_full_page_text(it.get("url", ""))
                if len(page_text) > len(it.get("full_text") or ""):
                    it["full_text"] = page_text

            analysis = llm.analyze(it)
            analyzed += 1
            # реквизит, который нашла модель, но пропустил regex
            extra_ref = analysis.get("npa_ref")
            if extra_ref:
                for k in dedupe.extract_npa_refs(str(extra_ref)):
                    if k not in it["npa_refs"]:
                        it["npa_refs"].append(k)

            try:
                final = int(analysis.get("relevance_score"))
            except (TypeError, ValueError):
                final = score
            if it["category"] == config.CAT_INTL:
                final = max(final, score)

            will_notify = final >= config.MIN_SCORE_FOR_NOTIFY
            store.save_item(it, final, analysis, it["npa_refs"], notified=False)
            if it["category"] == config.CAT_LAW and it["npa_refs"]:
                store.npa_register(it["npa_refs"], it)
            if will_notify:
                processed.append({"item": it, "score": score, "analysis": analysis})
            else:
                store.mark_seen(it)

        log.info("К отправке: %d (LLM-анализов: %d)", len(processed), analyzed)

        new_insight = insights.generate_law_insight(store)

        exported = export.export_all(store)
        try:
            import supabase_sync
            supabase_sync.sync_items(exported)
        except Exception as e:
            log.warning("Supabase sync FAIL: %s", e)

        sent = 0
        if send_telegram:
            sent = notify.send_report(processed)
            if new_insight:
                notify.send_insight(new_insight)
            log.info("Отправлено сообщений: %d | %s", sent, store.stats())

        # Релевантные помечаем seen только после успешной доставки (или в dry-режиме)
        if not send_telegram or not processed or sent > 0:
            for p in processed:
                store.mark_seen(p["item"])
                store.set_notified(dedupe.item_slug(p["item"]))
        else:
            log.warning("Доставка не удалась — %d позиций НЕ помечены seen", len(processed))
            _alert("Доставка в Telegram не удалась — проверь бота/канал")

        store.prune()
        _ping()
    except Exception:
        tb = traceback.format_exc()
        log.error("ЦИКЛ УПАЛ:\n%s", tb)
        _alert(tb)
        _ping(fail=True)
        raise
    finally:
        store.close()


# ─────────────────────────── Диагностика ───────────────────────────
def run_tests():
    print("── TA Tenders — тест ──")
    print("1. Telegram:", "OK" if notify.send_test() else "нет токена/чата или ошибка")
    wb = sources.fetch_worldbank(rows=5)
    print(f"2. World Bank API: {len(wb)}")
    ted = sources.fetch_ted(limit=5)
    print(f"3. EU TED API: {len(ted)} ({'вкл' if config.TED_ENABLED else 'выкл'})")
    lx = sources.fetch_lexuz_telegram(limit=5)
    print(f"4. lex.uz: {len(lx)}")
    tw = sources.fetch_tenderweek_public(pages=1)
    print(f"5. TenderWeek (публичный): {len(tw)}")
    un = sources.fetch_undp()
    print(f"6. UNDP: {len(un)}")
    print("7. Headless:", ("вкл: " + ",".join(config.HEADLESS_ON))
          if config.HEADLESS_ENABLED else "выкл (HEADLESS_ENABLED=0)")
    print("8. Anthropic ключ:", "задан" if config.ANTHROPIC_KEY else "НЕ задан (dry-режим)")
    print("9. SITE_BASE_URL:", config.SITE_BASE_URL or "не задан (кнопки на сайт выкл)")


def collect_only():
    items = sources.collect_all()
    by_cat = {}
    for it in items:
        by_cat[it["category"]] = by_cat.get(it["category"], 0) + 1
    print(f"Собрано {len(items)}:", by_cat)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--no-telegram", action="store_true",
                    help="полный цикл без отправки в Telegram")
    ap.add_argument("--export", action="store_true",
                    help="только перегенерировать web/data из базы")
    ap.add_argument("--insight", action="store_true",
                    help="принудительно сгенерировать аналитический дайджест НПА")
    args = ap.parse_args()

    setup_logging()
    if args.test:
        run_tests()
    elif args.collect:
        collect_only()
    elif args.insight:
        s = Store()
        result = insights.generate_law_insight(s, force=True)
        export.export_all(s)
        s.close()
        print("Инсайт:", result.get("title") if result else "не создан (см. лог)")
    elif args.export:
        s = Store()
        export.export_all(s)
        s.close()
    elif args.run:
        run(send_telegram=not args.no_telegram)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
