export const publicApiErrorCodes = [
  "rate_limited",
  "network_error",
  "contract_mismatch",
  "chain_not_found",
  "report_not_available",
  "validation_error",
  "no_snapshot_for_date",
  "future_as_of_date",
  "invalid_date_range",
  "range_too_large",
  "too_many_points",
  "series_not_available",
  "source_required",
  "unknown",
] as const;

export type PublicApiErrorCode = (typeof publicApiErrorCodes)[number];

export const publicApiErrorMessageKeys: Record<PublicApiErrorCode, string> = {
  rate_limited: "publicErrors.rateLimited",
  network_error: "publicErrors.network",
  contract_mismatch: "publicErrors.contractMismatch",
  chain_not_found: "publicErrors.chainNotFound",
  report_not_available: "publicErrors.reportNotAvailable",
  validation_error: "publicErrors.validation",
  no_snapshot_for_date: "publicErrors.noSnapshot",
  future_as_of_date: "publicErrors.futureDate",
  invalid_date_range: "publicErrors.range",
  range_too_large: "publicErrors.range",
  too_many_points: "publicErrors.range",
  series_not_available: "publicErrors.seriesUnavailable",
  source_required: "publicErrors.sourceRequired",
  unknown: "publicErrors.unknown",
};

export type PublicApiErrorMessageKey =
  (typeof publicApiErrorMessageKeys)[PublicApiErrorCode];

export function getPublicApiErrorMessageKey(code: string): string {
  return publicApiErrorMessageKeys[
    (publicApiErrorCodes as readonly string[]).includes(code)
      ? (code as PublicApiErrorCode)
      : "unknown"
  ];
}

function formatDuration(seconds: number, locale: "en" | "fa"): string {
  const units = [
    { seconds: 3600, en: ["hour", "hours"], fa: "ساعت" },
    { seconds: 60, en: ["minute", "minutes"], fa: "دقیقه" },
    { seconds: 1, en: ["second", "seconds"], fa: "ثانیه" },
  ] as const;
  let remainder = seconds;
  const parts: string[] = [];

  for (const unit of units) {
    const amount = Math.floor(remainder / unit.seconds);
    if (amount === 0) continue;
    remainder %= unit.seconds;
    parts.push(
      locale === "en"
        ? `${amount} ${unit.en[amount === 1 ? 0 : 1]}`
        : `${amount} ${unit.fa}`,
    );
  }

  return locale === "en" ? parts.join(" ") : parts.join(" و ");
}

export function getPublicApiErrorMessage(
  code: string,
  retryAfter: string | undefined,
  locale: "en" | "fa",
): { key: PublicApiErrorMessageKey; values?: { retryAfter: string } } {
  if (code === "rate_limited" && retryAfter && /^\d+$/.test(retryAfter)) {
    const seconds = Number.parseInt(retryAfter, 10);
    if (Number.isSafeInteger(seconds) && seconds > 0) {
      return {
        key: "publicErrors.rateLimitedRetry",
        values: { retryAfter: formatDuration(seconds, locale) },
      };
    }
  }

  return {
    key: getPublicApiErrorMessageKey(code) as PublicApiErrorMessageKey,
  };
}
