export const publicApiErrorCodes = [
  "rate_limited",
  "network_error",
  "contract_mismatch",
  "chain_not_found",
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

export function getPublicApiErrorMessageKey(code: string): string {
  return publicApiErrorMessageKeys[
    (publicApiErrorCodes as readonly string[]).includes(code)
      ? (code as PublicApiErrorCode)
      : "unknown"
  ];
}
