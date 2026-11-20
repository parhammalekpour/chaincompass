import type { ZodType } from "zod";
import {
  chainDetailResponseSchema,
  chainsResponseSchema,
  publicApiErrorSchema,
  scoreHistoryResponseSchema,
  type ChainDetailResponse,
  type ChainSlug,
  type ChainsResponse,
  type ScoreHistoryResponse,
} from "./contracts";
import {
  publicApiErrorCodes,
  type PublicApiErrorCode,
} from "./error-codes";

function isPublicApiErrorCode(code: string): code is PublicApiErrorCode {
  return (publicApiErrorCodes as readonly string[]).includes(code);
}

export class ApiError extends Error {
  readonly code: PublicApiErrorCode;
  readonly status: number;
  readonly retryAfter?: string;
  readonly serverMessage?: string;

  constructor(
    code: PublicApiErrorCode,
    status: number,
    options: { retryAfter?: string; serverMessage?: string } = {},
  ) {
    super(code);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.retryAfter = options.retryAfter;
    this.serverMessage = options.serverMessage;
  }
}

export class ContractError extends ApiError {
  constructor(readonly details: unknown) {
    super("contract_mismatch", 200);
    this.name = "ContractError";
  }
}

async function responseBody(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}

function apiErrorFromResponse(response: Response, body: unknown): ApiError {
  const parsed = publicApiErrorSchema.safeParse(body);
  const rawCode = parsed.success ? parsed.data.error.code : "unknown";
  const code =
    response.status === 429
      ? "rate_limited"
      : isPublicApiErrorCode(rawCode)
        ? rawCode
        : "unknown";

  return new ApiError(code, response.status, {
    retryAfter: response.headers.get("Retry-After") ?? undefined,
    serverMessage: parsed.success ? parsed.data.error.message : undefined,
  });
}

export async function fetchPublicData<T>(
  path: string,
  schema: ZodType<T>,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method: "GET",
      credentials: "omit",
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new ApiError("network_error", 0);
  }

  const body = await responseBody(response);
  if (!response.ok) throw apiErrorFromResponse(response, body);

  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    if (process.env.NODE_ENV === "development") {
      console.error("Public API contract mismatch", parsed);
    }
    throw new ContractError(parsed);
  }
  return parsed.data;
}

export function getChains(): Promise<ChainsResponse> {
  return fetchPublicData("/api/v1/chains", chainsResponseSchema);
}

export function getChainDetail(
  slug: ChainSlug,
): Promise<ChainDetailResponse> {
  return fetchPublicData(
    `/api/v1/chains/${encodeURIComponent(slug)}`,
    chainDetailResponseSchema,
  );
}

export function getScoreHistory(
  slug: ChainSlug,
  range: { from: string; to: string },
): Promise<ScoreHistoryResponse> {
  const params = new URLSearchParams({ from: range.from, to: range.to });
  return fetchPublicData(
    `/api/v1/chains/${encodeURIComponent(slug)}/score-history?${params}`,
    scoreHistoryResponseSchema,
  );
}
