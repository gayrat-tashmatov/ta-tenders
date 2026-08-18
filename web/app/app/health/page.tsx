import { getMeta } from "@/lib/data";

export const metadata = { title: "Источники | Кабинет TA Tenders" };
export const dynamic = "force-dynamic";

interface Health {
  origin: string;
  lastRun: string | null;
  lastCount: number;
  lastNonzero: string | null;
  total: number;
}

function ago(iso: string | null): string {
  if (!iso) return "никогда";
  const h = Math.floor((Date.now() - +new Date(iso)) / 3600000);
  if (h < 1) return "менее часа назад";
  if (h < 24) return `${h} ч назад`;
  const d = Math.floor(h / 24);
  return `${d} дн назад`;
}

function verdict(h: Health): { cls: string; text: string } {
  const sinceNZ = h.lastNonzero ? (Date.now() - +new Date(h.lastNonzero)) / 3600000 : Infinity;
  if (h.lastCount > 0) return { cls: "st-active", text: "работает" };
  if (sinceNZ < 48) return { cls: "", text: "тихо (нет новых)" };
  return { cls: "st-expiring", text: "⚠ давно молчит" };
}

export default function HealthPage() {
  const meta = getMeta() as ReturnType<typeof getMeta> & { health?: Health[] };
  const health = meta.health ?? [];
  const updated = meta.updatedAt ? new Date(meta.updatedAt) : null;
  return (
    <main className="container cab-section">
      <h1 className="page-title">Здоровье источников</h1>
      <p className="page-sub">
        Что и когда отдал каждый источник в последнем прогоне. Ноль у источника,
        который обычно активен, — сигнал поломки. Последний прогон:{" "}
        {updated ? updated.toLocaleString("ru-RU", { timeZone: "Asia/Tashkent" }) : "—"} (Ташкент).
        Расписание: 08:00 · 12:00 · 16:00 · 20:00.
      </p>
      {health.length === 0 && (
        <div className="empty">Статистика появится после следующего прогона.</div>
      )}
      {health.length > 0 && (
        <div className="section" style={{ overflowX: "auto" }}>
          <table className="health-table">
            <thead>
              <tr>
                <th>Источник</th>
                <th>Статус</th>
                <th>В последний прогон</th>
                <th>Последние данные</th>
                <th>Всего в базе</th>
              </tr>
            </thead>
            <tbody>
              {health.map((h) => {
                const v = verdict(h);
                return (
                  <tr key={h.origin}>
                    <td><b>{h.origin}</b></td>
                    <td><span className={`badge ${v.cls}`}>{v.text}</span></td>
                    <td>{h.lastCount}</td>
                    <td>{ago(h.lastNonzero)}</td>
                    <td>{h.total}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
