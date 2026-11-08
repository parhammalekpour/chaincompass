export type AppLocale = "en" | "fa";
type NumberOptions = Omit<Intl.NumberFormatOptions, "numberingSystem">;

function createNumberFormat(
  locale: AppLocale,
  options: NumberOptions = {},
): Intl.NumberFormat {
  return new Intl.NumberFormat(locale, {
    ...options,
    numberingSystem: "latn",
  });
}

export function formatNumber(
  value: number,
  locale: AppLocale,
  options: NumberOptions = {},
): string {
  return createNumberFormat(locale, options).format(value);
}

export function formatCurrency(
  value: number,
  locale: AppLocale,
  currency = "USD",
): string {
  return createNumberFormat(locale, {
    style: "currency",
    currency,
  }).format(value);
}

export function formatPercent(
  value: number,
  locale: AppLocale,
  options: NumberOptions = {},
): string {
  return createNumberFormat(locale, {
    style: "percent",
    maximumFractionDigits: 2,
    ...options,
  }).format(value);
}

export function formatCompact(value: number, locale: AppLocale): string {
  return createNumberFormat(locale, {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}
