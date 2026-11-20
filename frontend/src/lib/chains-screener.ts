import type { ChainSummary } from "@/lib/public-api/contracts";

export const screenerSortKeys = [
  "chain",
  "score",
  "regime",
  "volatility",
  "price",
  "return",
  "flags",
  "freshness",
] as const;

export type ScreenerSortKey = (typeof screenerSortKeys)[number];
export type ScreenerDirection = "asc" | "desc";
export type ScreenerRegime = "all" | "uptrend" | "downtrend" | "range";
export type ScreenerConfidence = "all" | "High" | "Medium" | "Low";

export type ScreenerState = {
  sort: ScreenerSortKey;
  direction: ScreenerDirection;
  regime: ScreenerRegime;
  confidence: ScreenerConfidence;
  hasRiskFlags: boolean;
};

export const defaultScreenerState: ScreenerState = {
  sort: "chain",
  direction: "asc",
  regime: "all",
  confidence: "all",
  hasRiskFlags: false,
};

const regimes: readonly ScreenerRegime[] = [
  "all",
  "uptrend",
  "downtrend",
  "range",
];
const confidences: readonly ScreenerConfidence[] = [
  "all",
  "High",
  "Medium",
  "Low",
];

export function parseScreenerParams(search: string): ScreenerState {
  const params = new URLSearchParams(
    search.startsWith("?") ? search.slice(1) : search,
  );
  const sort = params.get("sort");
  const regime = params.get("regime");
  const confidence = params.get("confidence");
  return {
    sort:
      sort && (screenerSortKeys as readonly string[]).includes(sort)
        ? (sort as ScreenerSortKey)
        : defaultScreenerState.sort,
    direction: params.get("direction") === "desc" ? "desc" : "asc",
    regime:
      regime && (regimes as readonly string[]).includes(regime)
        ? (regime as ScreenerRegime)
        : "all",
    confidence:
      confidence && (confidences as readonly string[]).includes(confidence)
        ? (confidence as ScreenerConfidence)
        : "all",
    hasRiskFlags: params.get("risk") === "true",
  };
}

export function serializeScreenerParams(state: ScreenerState): string {
  return new URLSearchParams({
    sort: state.sort,
    direction: state.direction,
    regime: state.regime,
    confidence: state.confidence,
    risk: String(state.hasRiskFlags),
  }).toString();
}

function compareDecimalStrings(left: string, right: string): number {
  const parse = (value: string) => {
    const negative = value.startsWith("-");
    const unsigned = negative ? value.slice(1) : value;
    const [integer = "0", fraction = ""] = unsigned.split(".");
    return {
      negative,
      integer: integer.replace(/^0+(?=\d)/, ""),
      fraction: fraction.replace(/0+$/, ""),
    };
  };
  const a = parse(left);
  const b = parse(right);
  if (a.negative !== b.negative) return a.negative ? -1 : 1;
  const sign = a.negative ? -1 : 1;
  if (a.integer.length !== b.integer.length) {
    return (a.integer.length < b.integer.length ? -1 : 1) * sign;
  }
  const integerOrder = a.integer.localeCompare(b.integer);
  if (integerOrder !== 0) return integerOrder * sign;
  const fractionLength = Math.max(a.fraction.length, b.fraction.length);
  return (
    a.fraction.padEnd(fractionLength, "0").localeCompare(
      b.fraction.padEnd(fractionLength, "0"),
    ) * sign
  );
}

function compareValues(left: string | number, right: string | number): number {
  return typeof left === "number" && typeof right === "number"
    ? left - right
    : String(left).localeCompare(String(right));
}

function sortValue(
  chain: ChainSummary,
  sort: ScreenerSortKey,
): string | number | null {
  switch (sort) {
    case "chain":
      return chain.name;
    case "score":
      return chain.score?.value ?? null;
    case "regime":
      return chain.regime?.label ?? null;
    case "volatility":
      return chain.regime?.vol_state ?? null;
    case "price":
      return chain.price.close_usd;
    case "return":
      return chain.price.ret_30d;
    case "flags":
      return chain.flags.length;
    case "freshness":
      return chain.freshness.price_last_date;
  }
}

function compareSortableValues(
  sort: ScreenerSortKey,
  left: string | number,
  right: string | number,
): number {
  if (
    (sort === "score" || sort === "price" || sort === "return") &&
    typeof left === "string" &&
    typeof right === "string"
  ) {
    return compareDecimalStrings(left, right);
  }
  return compareValues(left, right);
}

export function filterAndSortChains(
  chains: readonly ChainSummary[],
  state: ScreenerState,
): ChainSummary[] {
  const filtered = chains.filter((chain) => {
    if (state.regime !== "all" && chain.regime?.label !== state.regime) {
      return false;
    }
    if (
      state.confidence !== "all" &&
      chain.score?.confidence_label !== state.confidence
    ) {
      return false;
    }
    return !state.hasRiskFlags || chain.flags.length > 0;
  });

  return filtered
    .map((chain, index) => ({ chain, index, value: sortValue(chain, state.sort) }))
    .sort((left, right) => {
      if (left.value === null || right.value === null) {
        if (left.value === right.value) return left.index - right.index;
        return left.value === null ? 1 : -1;
      }
      const order = compareSortableValues(state.sort, left.value, right.value);
      if (order === 0) return left.index - right.index;
      return state.direction === "asc" ? order : -order;
    })
    .map(({ chain }) => chain);
}