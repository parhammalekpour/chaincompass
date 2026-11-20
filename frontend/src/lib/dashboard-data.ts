import type {
  ChainSlug,
  ScoreHistoryItem,
} from "@/lib/public-api/contracts";

export type ScoreHistoryRange = "1y" | "3y" | "max";
export type ScoreHistorySeries = {
  slug: ChainSlug;
  items: ScoreHistoryItem[];
};

export type ScoreHistoryChartPoint = {
  date: string;
  btc: number | null;
  btcConfidence?: string;
  btcPartial?: boolean;
  eth: number | null;
  ethConfidence?: string;
  ethPartial?: boolean;
  sol: number | null;
  solConfidence?: string;
  solPartial?: boolean;
  bnb: number | null;
  bnbConfidence?: string;
  bnbPartial?: boolean;
};

const RANGE_DAYS: Record<ScoreHistoryRange, number> = {
  "1y": 365,
  "3y": 1095,
  max: 3650,
};

const CHAIN_SLUGS: readonly ChainSlug[] = ["btc", "eth", "sol", "bnb"];

export function getScoreHistoryDateRange(
  range: ScoreHistoryRange,
  now = new Date(),
): { from: string; to: string } {
  const toDate = new Date(
    Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()),
  );
  const fromDate = new Date(toDate);
  fromDate.setUTCDate(fromDate.getUTCDate() - RANGE_DAYS[range] + 1);
  return {
    from: fromDate.toISOString().slice(0, 10),
    to: toDate.toISOString().slice(0, 10),
  };
}

export function buildScoreHistoryChartData(
  series: readonly ScoreHistorySeries[],
  range: { from: string; to: string },
): ScoreHistoryChartPoint[] {
  const byChain = new Map(
    series.map(({ slug, items }) => [
      slug,
      new Map(items.map((item) => [item.as_of_date, item])),
    ]),
  );
  const points: ScoreHistoryChartPoint[] = [];
  const current = new Date(`${range.from}T00:00:00.000Z`);
  const end = new Date(`${range.to}T00:00:00.000Z`);

  while (current <= end) {
    const date = current.toISOString().slice(0, 10);
    const point: ScoreHistoryChartPoint = {
      date,
      btc: null,
      eth: null,
      sol: null,
      bnb: null,
    };

    for (const slug of CHAIN_SLUGS) {
      const item = byChain.get(slug)?.get(date);
      if (!item) continue;
      const value = Number(item.score);
      point[slug] = Number.isFinite(value) ? value : null;
      point[`${slug}Confidence`] = item.confidence_label;
      point[`${slug}Partial`] = item.is_partial;
    }

    points.push(point);
    current.setUTCDate(current.getUTCDate() + 1);
  }

  return points;
}

function parseDisplayDecimal(value: string | null): number | null {
  if (value === null) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatCompactUsd(value: string | null): string {
  const parsed = parseDisplayDecimal(value);
  if (parsed === null) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(parsed);
}

export function formatSignedPercent(value: string | null): string {
  const parsed = parseDisplayDecimal(value);
  if (parsed === null) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "percent",
    signDisplay: "always",
    maximumFractionDigits: 2,
  }).format(parsed);
}

export function formatScore(value: string): string {
  const parsed = parseDisplayDecimal(value);
  if (parsed === null) return "—";
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(parsed);
}

export function formatCoverage(value: string): string {
  const parsed = parseDisplayDecimal(value);
  if (parsed === null) return "—";
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 0,
  }).format(parsed * 100);
}

export function freshestPriceDate(
  dates: readonly (string | null)[],
): string | null {
  return dates.reduce<string | null>(
    (latest, date) => (date && (!latest || date > latest) ? date : latest),
    null,
  );
}