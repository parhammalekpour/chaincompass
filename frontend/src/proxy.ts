import createMiddleware from "next-intl/middleware";
import { NextRequest, NextResponse } from "next/server";
import { routing } from "./i18n/routing";

const handleI18nRouting = createMiddleware(routing);
const supportedLocales: readonly string[] = routing.locales;

export default function proxy(request: NextRequest) {
  if (request.nextUrl.pathname === "/") {
    const cookieLocale = request.cookies.get("NEXT_LOCALE")?.value;
    const locale = supportedLocales.includes(cookieLocale ?? "")
      ? cookieLocale
      : routing.defaultLocale;

    return NextResponse.redirect(new URL(`/${locale}`, request.url));
  }

  return handleI18nRouting(request);
}

export const config = {
  matcher: ["/((?!api|trpc|_next|_vercel|.*\\..*).*)"],
};
