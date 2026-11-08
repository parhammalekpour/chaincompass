export function getLocaleTargetPath(
  pathname: string,
  query: string,
  locale: "en" | "fa",
) {
  const localizedPath =
    pathname.replace(/^\/(en|fa)(?=\/|$)/, "") || "/";
  return `/${locale}${localizedPath === "/" ? "" : localizedPath}${query}`;
}

export function changeLocale(
  pathname: string,
  query: string,
  locale: "en" | "fa",
  navigate: (target: string) => void = (target) =>
    window.location.assign(target),
) {
  document.cookie = `NEXT_LOCALE=${locale}; Path=/; Max-Age=31536000; SameSite=Lax`;
  navigate(getLocaleTargetPath(pathname, query, locale));
}
