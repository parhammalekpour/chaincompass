const ENCODED_SEPARATOR = /%(?:2f|5c)/i;

export function sanitizeNextPath(value: string | null, locale: string): string {
  const safeLocale = locale === "fa" ? "fa" : "en";
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return `/${safeLocale}/app`;
  }

  let decoded = value;
  for (let index = 0; index < 3; index += 1) {
    if (ENCODED_SEPARATOR.test(decoded)) return `/${safeLocale}/app`;
    try {
      const next = decodeURIComponent(decoded);
      if (next === decoded) break;
      decoded = next;
    } catch {
      return `/${safeLocale}/app`;
    }
  }

  if (
    !decoded.startsWith("/") ||
    decoded.startsWith("//") ||
    decoded.includes("\\") ||
    /^[a-z][a-z\d+.-]*:/i.test(decoded)
  ) {
    return `/${safeLocale}/app`;
  }

  const localePrefix = /^\/(en|fa)(?:\/|$)/.exec(decoded);
  if (localePrefix) return value;
  return `/${safeLocale}${value}`;
}
