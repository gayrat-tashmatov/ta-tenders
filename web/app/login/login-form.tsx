"use client";

import { useActionState } from "react";
import { signIn } from "./actions";

export function LoginForm({ next }: { next: string }) {
  const [state, action, pending] = useActionState(signIn, null);
  return (
    <div className="login-wrap">
      <form className="login-card" action={action}>
        <input type="hidden" name="next" value={next} />
        <div className="login-brand">
          TopAdvisor <span>· Tenders</span>
        </div>
        <h1>Вход в кабинет</h1>
        <p className="login-sub">
          Мониторинг тендеров, донорских проектов и НПА. Доступ только для
          команды — аккаунты выдаёт администратор.
        </p>
        <label>
          E-mail
          <input
            name="email"
            type="email"
            autoComplete="username"
            placeholder="you@topadvisor.biz"
            required
          />
        </label>
        <label>
          Пароль
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            required
          />
        </label>
        {state?.error && <div className="login-error">{state.error}</div>}
        <button className="btn wide" disabled={pending}>
          {pending ? "Входим…" : "Войти"}
        </button>
      </form>
    </div>
  );
}
