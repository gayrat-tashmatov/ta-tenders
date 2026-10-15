"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { markSeenNow } from "./actions";

export function SeenButton({ count, scope }: { count: number; scope: string }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [err, setErr] = useState<string | null>(null);
  if (count === 0) return <span className="muted small">Новых нет — всё просмотрено</span>;
  return (
    <span className="seen-wrap">
      <button
        className="btn"
        disabled={pending}
        onClick={() =>
          start(async () => {
            const r = await markSeenNow(scope);
            if (!r.ok) setErr(r.error ?? "Не сохранилось");
            else router.refresh();
          })
        }
      >
        {pending ? "Отмечаю…" : `✓ Отметить всё просмотренным (${count})`}
      </button>
      {err && <span className="err small">⚠ {err}</span>}
    </span>
  );
}
