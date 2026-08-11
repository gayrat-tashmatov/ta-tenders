import { LoginForm } from "./login-form";

export const metadata = { title: "Вход | TA Tenders" };

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const { next } = await searchParams;
  const safeNext = next && next.startsWith("/") ? next : "/app";
  return <LoginForm next={safeNext} />;
}
