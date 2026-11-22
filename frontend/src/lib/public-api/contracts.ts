import { z } from "zod";

const dateSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
const decimalStringSchema = z.string().regex(/^-?\d+(?:\.\d+)?$/);
export const chainSlugSchema = z.enum(["btc", "eth", "sol", "bnb"]);
const confidenceSchema = z.enum(["High", "Medium", "Low"]);

export const flagSummarySchema = z
  .object({
    flag: z.string(),
    severity: z.string(),
  })
  .strict();

export const regimeSchema = z
  .object({
    label: z.string(),
    days_in_regime: z.number().int().nonnegative(),
    vol_state: z.string().nullable(),
  })
  .strict();

export const freshnessSchema = z
  .object({
    price_last_date: dateSchema.nullable(),
    lag_days: z.number().int().nullable(),
    stale: z.boolean(),
  })
  .strict();

export const priceSchema = z
  .object({
    close_usd: decimalStringSchema.nullable(),
    as_of_date: dateSchema.nullable(),
    ret_30d: decimalStringSchema.nullable(),
  })
  .strict();

export const scoreSummarySchema = z
  .object({
    value: decimalStringSchema,
    as_of_date: dateSchema,
    coverage: decimalStringSchema,
    coverage_max: decimalStringSchema,
    is_partial: z.boolean(),
    confidence_label: confidenceSchema,
    version: z.string(),
  })
  .strict();

export const chainSummarySchema = z
  .object({
    slug: chainSlugSchema,
    name: z.string(),
    symbol: z.string(),
    price: priceSchema,
    score: scoreSummarySchema.nullable(),
    regime: regimeSchema.nullable(),
    flags: z.array(flagSummarySchema),
    freshness: freshnessSchema,
  })
  .strict();

export const chainsResponseSchema = z
  .object({
    generated_at: z.string().datetime({ offset: true }),
    analysis_only: z.literal(true),
    chains: z.array(chainSummarySchema),
  })
  .strict();

export const scoreHistoryItemSchema = z
  .object({
    as_of_date: dateSchema,
    score: decimalStringSchema,
    coverage: decimalStringSchema,
    is_partial: z.boolean(),
    confidence_label: confidenceSchema,
  })
  .strict();

export const scoreHistoryResponseSchema = z
  .object({
    generated_at: z.string().datetime({ offset: true }),
    analysis_only: z.literal(true),
    chain: chainSlugSchema,
    items: z.array(scoreHistoryItemSchema),
  })
  .strict();

const flagDetailSchema = flagSummarySchema.extend({
  value: decimalStringSchema,
  threshold: decimalStringSchema,
});

const lastFullCoverageSchema = z
  .object({
    value: decimalStringSchema,
    as_of_date: dateSchema,
    coverage: decimalStringSchema,
    confidence_label: confidenceSchema,
  })
  .strict();

const dataCoverageSchema = z
  .object({
    metric: z.string(),
    source: z.string(),
    role: z.enum(["score", "context"]),
    first_date: dateSchema.nullable(),
    last_date: dateSchema.nullable(),
    points: z.number().int().nonnegative(),
    missing: z.number().int().nonnegative(),
    status: z.string(),
    derived: z.boolean(),
    note: z.string(),
  })
  .strict();

const scoreDetailSchema = scoreSummarySchema.extend({
  pillars: z.record(
    z.string(),
    z
      .object({
        score: decimalStringSchema.nullable(),
        available: z.boolean(),
        weight_used: z.number().int().nonnegative(),
      })
      .strict(),
  ),
  components: z.array(
    z
      .object({
        value: decimalStringSchema,
        weight: z.number().int().nonnegative(),
        feature: z.string(),
        direction: z.enum(["higher_is_better", "lower_is_better"]),
        percentile: decimalStringSchema,
      })
      .strict(),
  ),
});

export const chainDetailResponseSchema = z
  .object({
    generated_at: z.string().datetime({ offset: true }),
    analysis_only: z.literal(true),
    slug: chainSlugSchema,
    name: z.string(),
    symbol: z.string(),
    price: priceSchema,
    score: scoreDetailSchema.nullable(),
    regime: regimeSchema.nullable(),
    flags: z.array(flagDetailSchema),
    freshness: freshnessSchema,
    last_full_coverage: lastFullCoverageSchema.nullable().optional(),
    data_coverage: z.array(dataCoverageSchema),
    methodology_version: z.string(),
  })
  .strict();

export const regimeSegmentSchema = z
  .object({
    regime: z.string(),
    start_date: dateSchema,
    end_date: dateSchema,
    days: z.number().int().positive(),
  })
  .strict();

export const regimesResponseSchema = z
  .object({
    generated_at: z.string().datetime({ offset: true }),
    analysis_only: z.literal(true),
    chain: chainSlugSchema,
    segments: z.array(regimeSegmentSchema),
    latest_vol_state: z.string().nullable(),
  })
  .strict();

export const seriesPointSchema = z
  .object({
    date: dateSchema,
    value: decimalStringSchema,
  })
  .strict();

export const seriesMetaSchema = z
  .object({
    chain: chainSlugSchema,
    metric: z.string(),
    source: z.string(),
    role: z.enum(["score", "context"]),
    derived: z.boolean(),
    status: z.string(),
    first_date: dateSchema.nullable(),
    last_date: dateSchema.nullable(),
    points: z.number().int().nonnegative(),
    missing: z.number().int().nonnegative(),
    unit_note: z.string(),
  })
  .strict();

export const seriesResponseSchema = z
  .object({
    generated_at: z.string().datetime({ offset: true }),
    analysis_only: z.literal(true),
    meta: seriesMetaSchema,
    points: z.array(seriesPointSchema),
  })
  .strict();

export const scenarioValueSchema = z
  .object({
    name: z.enum(["pessimistic", "base", "optimistic"]),
    quantile: z.enum(["p10", "p50", "p90"]),
    return: decimalStringSchema,
    illustrative_price_usd: decimalStringSchema,
  })
  .strict();

export const scenarioHorizonSchema = z
  .object({
    days: z.number().int().positive(),
    available: z.boolean(),
    reason: z.string().nullable(),
    low_sample: z.boolean(),
    n_windows: z.number().int().nonnegative(),
    n_independent: z.number().int().nonnegative(),
    first_window_start: dateSchema.nullable(),
    last_window_end: dateSchema.nullable(),
    share_negative: decimalStringSchema.nullable(),
    scenarios: z.array(scenarioValueSchema),
  })
  .strict();

export const scenariosResponseSchema = z
  .object({
    generated_at: z.string().datetime({ offset: true }),
    analysis_only: z.literal(true),
    chain: chainSlugSchema,
    version: z.string(),
    as_of_date: dateSchema,
    base_price: z
      .object({
        close_usd: decimalStringSchema,
        date: dateSchema,
      })
      .strict(),
    horizons: z.array(scenarioHorizonSchema),
    not_a_forecast: z.literal(true),
    method_note: z.string(),
    disclaimer: z.string(),
  })
  .strict();

export const reportIndicatorStatusSchema = z.enum([
  "available",
  "not_available",
  "not_applicable",
]);
export const reportIndicatorGroupSchema = z.enum([
  "market",
  "capital",
  "usage",
  "security",
]);
export const reportDataGapStatusSchema = z.enum([
  "not_available",
  "not_applicable",
  "not_available_free",
]);

export const fundamentalReportResponseSchema = z
  .object({
    chain: chainSlugSchema,
    as_of_date: dateSchema,
    methodology_version: z.string(),
    generated_from: z.literal("stored_data"),
    health: z
      .object({
        score: decimalStringSchema,
        confidence: confidenceSchema,
        coverage: decimalStringSchema,
        score_30d_ago: decimalStringSchema.nullable(),
        score_90d_ago: decimalStringSchema.nullable(),
        change_30d: decimalStringSchema.nullable(),
        change_90d: decimalStringSchema.nullable(),
      })
      .passthrough(),
    regime: z
      .object({
        regime: z.string().nullable(),
        vol_state: z.string().nullable(),
        since_date: dateSchema.nullable(),
        days_in_regime: z.number().int().nonnegative().nullable(),
        history_gap: z.boolean(),
      })
      .passthrough(),
    flags: z.array(
      z
        .object({
          code: z.string(),
          severity: z.enum(["info", "medium", "high"]),
        })
        .passthrough(),
    ),
    indicators: z.array(
      z
        .object({
          key: z.string(),
          group: reportIndicatorGroupSchema,
          value: decimalStringSchema.nullable(),
          percentile: decimalStringSchema.nullable(),
          status: reportIndicatorStatusSchema,
        })
        .passthrough(),
    ),
    data_gaps: z.array(
      z
        .object({
          key: z.string(),
          status: reportDataGapStatusSchema,
        })
        .passthrough(),
    ),
  })
  .passthrough();

const methodologyComponentSchema = z
  .object({
    feature: z.string(),
    weight: z.number().int().nonnegative(),
    direction: z.string(),
    chains: z.array(chainSlugSchema),
    derived_label: z.string().nullable(),
  })
  .strict();

const methodologyPillarSchema = z
  .object({
    name: z.string(),
    weight: z.number().int().nonnegative(),
    components: z.array(methodologyComponentSchema),
  })
  .strict();

export const methodologyResponseSchema = z
  .object({
    generated_at: z.string().datetime({ offset: true }),
    analysis_only: z.literal(true),
    version: z.string(),
    pillars: z.array(methodologyPillarSchema),
    sources: z
      .array(
        z
          .object({
            name: z.string(),
            used_for: z.array(z.string()),
          })
          .passthrough(),
      ),
  })
  .passthrough();

export const publicApiErrorSchema = z
  .object({
    error: z
      .object({
        code: z.string(),
        message: z.string(),
      })
      .strict(),
  })
  .strict();

export type ChainSlug = z.infer<typeof chainSlugSchema>;
export type ChainSummary = z.infer<typeof chainSummarySchema>;
export type ChainsResponse = z.infer<typeof chainsResponseSchema>;
export type ChainDetailResponse = z.infer<typeof chainDetailResponseSchema>;
export type ScoreHistoryResponse = z.infer<typeof scoreHistoryResponseSchema>;
export type ScoreHistoryItem = z.infer<typeof scoreHistoryItemSchema>;
export type RegimeSegment = z.infer<typeof regimeSegmentSchema>;
export type RegimesResponse = z.infer<typeof regimesResponseSchema>;
export type SeriesResponse = z.infer<typeof seriesResponseSchema>;
export type ScenariosResponse = z.infer<typeof scenariosResponseSchema>;
export type ScenarioHorizon = z.infer<typeof scenarioHorizonSchema>;
export type FundamentalReportResponse = z.infer<
  typeof fundamentalReportResponseSchema
>;
export type ReportIndicatorStatus = z.infer<
  typeof reportIndicatorStatusSchema
>;
export type MethodologyResponse = z.infer<typeof methodologyResponseSchema>;
