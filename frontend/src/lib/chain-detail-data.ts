import type {
  RegimeSegment,
  ScoreHistoryItem,
  SeriesResponse,
} from "@/lib/public-api/contracts";

export type ChainChartPoint = {
  date: string;
  value: number | null;
  confidence?: string;
  partial?: boolean;
};
type SeriesPoint = SeriesResponse["points"][number];

function nextUtcDate(date: string): string {
  const next = new Date(`${date}T00:00:00.000Z`);
  next.setUTCDate(next.getUTCDate() + 1);
  return next.toISOString().slice(0, 10);
}

function chartValue(value: string): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function buildContinuousSeries(
  points: readonly { date: string; value: string }[],
): ChainChartPoint[] {
  if (points.length === 0) return [];

  const byDate = new Map(points.map((point) => [point.date, point.value]));
  const dates = points.map((point) => point.date).sort();
  const first = dates[0];
  const last = dates[dates.length - 1];
  if (!first || !last) return [];

  const result: ChainChartPoint[] = [];
  let date = first;
  while (date <= last) {
    const value = byDate.get(date);
    result.push({
      date,
      value: value === undefined ? null : chartValue(value),
    });
    date = nextUtcDate(date);
  }
  return result;
}

export function buildChainScoreHistoryData(
  items: readonly ScoreHistoryItem[],
  range: { from: string; to: string },
): ChainChartPoint[] {
  const byDate = new Map(items.map((item) => [item.as_of_date, item]));
  const result: ChainChartPoint[] = [];
  let date = range.from;
  while (date <= range.to) {
    const item = byDate.get(date);
    result.push({
      date,
      value: item === undefined ? null : chartValue(item.score),
      ...(item && {
        confidence: item.confidence_label,
        partial: item.is_partial,
      }),
    });
    date = nextUtcDate(date);
  }
  return result;
}

export function buildPriceSeriesData(
  points: readonly SeriesPoint[],
): ChainChartPoint[] {
  return buildContinuousSeries(points);
}

export type RegimeTimelineItem = RegimeSegment;

export function buildRegimeTimeline(
  segments: readonly RegimeSegment[],
): RegimeTimelineItem[] {
  const ordered = [...segments].sort((a, b) =>
    a.start_date.localeCompare(b.start_date),
  );
  const result: RegimeTimelineItem[] = [];

  for (const segment of ordered) {
    const previous = result[result.length - 1];
    if (
      previous &&
      previous.regime === segment.regime &&
      nextUtcDate(previous.end_date) === segment.start_date
    ) {
      result[result.length - 1] = {
        ...previous,
        end_date: segment.end_date,
        days: previous.days + segment.days,
      };
    } else {
      result.push({ ...segment });
    }
  }

  return result;
}
