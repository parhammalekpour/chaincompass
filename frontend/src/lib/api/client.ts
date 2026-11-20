import {
  backendErrorCodes,
  backendErrorMessageKeys,
  type BackendErrorCode,
} from "./error-codes";

export type AuthUser = {
  id: string;
  email: string;
  locale: "en" | "fa";
  role: "user" | "admin";
  email_verified?: boolean;
};

export type AuthResponse = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: AuthUser;
};

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly retryAfterSeconds?: number;

  constructor(
    code: string,
    status: number,
    retryAfterSeconds?: number,
  ) {
    super(code);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

export class NetworkError extends Error {
  constructor() {
    super("network_error");
    this.name = "NetworkError";
  }
}

let accessToken: string | null = null;
let refreshInFlight: Promise<AuthResponse> | null = null;
const invalidationListeners = new Set<() => void>();

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function clearAccessToken() {
  accessToken = null;
  invalidationListeners.forEach((listener) => listener());
}

export function subscribeToSessionInvalidation(listener: () => void) {
  invalidationListeners.add(listener);
  return () => invalidationListeners.delete(listener);
}

function csrfCookie(): string | null {
  if (typeof document === "undefined") return null;
  const cookie = document.cookie
    .split("; ")
    .find((item) => item.startsWith("chaincompass_csrf="));
  return cookie ? decodeURIComponent(cookie.slice("chaincompass_csrf=".length)) : null;
}

function knownBackendCode(code: string): code is BackendErrorCode {
  return (backendErrorCodes as readonly string[]).includes(code);
}

async function responseJson(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined;
  const contentType = response.headers.get("Content-Type")?.toLowerCase() ?? "";
  if (
    !contentType.includes("application/json") &&
    !contentType.includes("+json")
  ) {
    throw new ApiError("http_error", response.status, retryAfter(response));
  }
  try {
    return await response.json();
  } catch {
    throw new ApiError("http_error", response.status, retryAfter(response));
  }
}

function retryAfter(response: Response): number | undefined {
  const value = response.headers.get("Retry-After");
  if (!value) return undefined;
  const seconds = Number(value);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : undefined;
}

async function decodeResponse<T>(response: Response): Promise<T> {
  const data = await responseJson(response);
  if (!response.ok) {
    const errorData =
      typeof data === "object" && data !== null
        ? (data as { error?: { code?: unknown } }).error
        : undefined;
    const rawCode =
      typeof errorData?.code === "string" ? errorData.code : "http_error";
    const code = knownBackendCode(rawCode) ? rawCode : "http_error";
    throw new ApiError(code, response.status, retryAfter(response));
  }
  return data as T;
}

async function performRefresh(signal?: AbortSignal): Promise<AuthResponse> {
  const csrf = csrfCookie();
  if (!csrf) {
    clearAccessToken();
    throw new ApiError("invalid_access_token", 401);
  }

  let response: Response;
  try {
    response = await fetch("/api/v1/auth/refresh", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRF-Token": csrf },
      signal,
    });
  } catch {
    clearAccessToken();
    throw new NetworkError();
  }

  try {
    const auth = await decodeResponse<AuthResponse>(response);
    setAccessToken(auth.access_token);
    return auth;
  } catch (error) {
    clearAccessToken();
    throw error;
  }
}

async function refreshAccessToken(
  signal?: AbortSignal,
): Promise<AuthResponse> {
  if (signal) return performRefresh(signal);
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = performRefresh();
  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

export async function refreshSession(
  signal?: AbortSignal,
): Promise<AuthResponse | null> {
  if (!csrfCookie()) {
    clearAccessToken();
    return null;
  }
  return refreshAccessToken(signal);
}

export type ApiRequestOptions = {
  method?: string;
  body?: unknown;
  headers?: HeadersInit;
  authRetry?: boolean;
  signal?: AbortSignal;
};

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const {
    method = "GET",
    body,
    headers,
    authRetry = true,
    signal,
  } = options;
  const makeRequest = async () => {
    const requestHeaders = new Headers(headers);
    const tokenUsed = accessToken;
    requestHeaders.set("Accept", "application/json");
    if (body !== undefined) requestHeaders.set("Content-Type", "application/json");
    if (tokenUsed) requestHeaders.set("Authorization", `Bearer ${tokenUsed}`);

    try {
      return {
        response: await fetch(path, {
          method,
          credentials: "same-origin",
          headers: requestHeaders,
          body: body === undefined ? undefined : JSON.stringify(body),
          signal,
        }),
        tokenUsed,
      };
    } catch {
      throw new NetworkError();
    }
  };

  let { response, tokenUsed } = await makeRequest();
  if (response.status === 401 && authRetry) {
    if (accessToken === tokenUsed) await refreshAccessToken(signal);
    ({ response, tokenUsed } = await makeRequest());
    if (response.status === 401) clearAccessToken();
  }
  return decodeResponse<T>(response);
}

export async function fetchAuthResponse(
  path: "/api/v1/auth/login",
  body: { email: string; password: string },
): Promise<AuthResponse> {
  const auth = await apiRequest<AuthResponse>(path, {
    method: "POST",
    body,
    authRetry: false,
  });
  setAccessToken(auth.access_token);
  return auth;
}

export async function logoutRequest(): Promise<void> {
  const csrf = csrfCookie();
  if (!csrf) throw new ApiError("csrf_failed", 403);
  await apiRequest<void>("/api/v1/auth/logout", {
    method: "POST",
    headers: { "X-CSRF-Token": csrf },
    authRetry: false,
  });
}

export function getCsrfCookie(): string | null {
  return csrfCookie();
}

export function getErrorMessageKey(error: unknown): string {
  if (error instanceof NetworkError) return "authErrors.network";
  if (error instanceof ApiError) {
    if (knownBackendCode(error.code)) return backendErrorMessageKeys[error.code];
  }
  return "authErrors.generic";
}
