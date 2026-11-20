import { z } from "zod";

const dateSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
const decimalStringSchema = z.string().regex(/^-?\d+(?:\.\d+)?$/);
const chainSlugSchema = z.enum(["btc", "eth", "sol", "bnb"]);
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
  pillars: z.record(z.string(), z.unknown()),
  components: z.array(z.record(z.string(), z.unknown())),
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
