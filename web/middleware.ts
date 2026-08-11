import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";

const URL_ = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

export async function middleware(req: NextRequest) {
  if (!URL_ || !ANON) {
    // Ключей нет: локально — демо открыт; на проде кабинет закрыт
    if (
      process.env.NODE_ENV === "production" &&
      req.nextUrl.pathname.startsWith("/app")
    ) {
      const url = req.nextUrl.clone();
      url.pathname = "/login";
      return NextResponse.redirect(url);
    }
    return NextResponse.next();
  }

  let res = NextResponse.next({ request: req });
  const supabase = createServerClient(URL_, ANON, {
    cookies: {
      getAll: () => req.cookies.getAll(),
      setAll: (all) => {
        for (const { name, value } of all) req.cookies.set(name, value);
        res = NextResponse.next({ request: req });
        for (const { name, value, options } of all)
          res.cookies.set(name, value, options);
      },
    },
  });
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const isApp = req.nextUrl.pathname.startsWith("/app");
  const isLogin = req.nextUrl.pathname.startsWith("/login");
  if (isApp && !user) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }
  if (isLogin && user) {
    const url = req.nextUrl.clone();
    url.pathname = "/app";
    return NextResponse.redirect(url);
  }
  return res;
}

export const config = {
  matcher: ["/app/:path*", "/login"],
};
