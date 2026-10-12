const SESSION_CORRELATION_ID = crypto.randomUUID();

// Signed Mini App launch data; the backend verifies it and takes the user from it.
function getTelegramInitData(): string | undefined {
  return window.Telegram?.WebApp?.initData || undefined;
}

// Unsigned user ID for dev builds outside Telegram. Accepted only by a backend
// running with ALLOW_INSECURE_USER_ID_HEADER=true.
function getDevUserId(): string | undefined {
  return import.meta.env.DEV
    ? (import.meta.env.VITE_DEV_USER_ID ?? "59357664")
    : undefined;
}

// IANA zone (e.g. "America/New_York") the backend uses to bucket meals into
// the user's local calendar days.
function getTimeZone(): string | undefined {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
  } catch {
    return undefined;
  }
}

function getBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
}

export async function customFetch<T>(
  urlOrConfig:
    | string
    | {
        url: string;
        method: string;
        params?: Record<string, string>;
        data?: unknown;
        headers?: Record<string, string>;
        signal?: AbortSignal;
      },
  init?: RequestInit,
): Promise<T> {
  const baseUrl = getBaseUrl();

  let fullUrl: string;
  let method: string;
  let body: string | undefined;
  let extraHeaders: Record<string, string> | undefined;
  let signal: AbortSignal | undefined;

  if (typeof urlOrConfig === "string") {
    // Orval-generated call: customFetch(url, { method, headers, body, signal })
    fullUrl = `${baseUrl}${urlOrConfig}`;
    method = init?.method ?? "GET";
    body = init?.body as string | undefined;
    extraHeaders = init?.headers as Record<string, string> | undefined;
    signal = init?.signal ?? undefined;
  } else {
    // Legacy call: customFetch({ url, method, params, data, ... })
    const {
      url,
      params,
      data,
      headers: cfgHeaders,
      signal: cfgSignal,
    } = urlOrConfig;
    method = urlOrConfig.method;
    const queryString = params
      ? "?" + new URLSearchParams(params).toString()
      : "";
    fullUrl = `${baseUrl}${url}${queryString}`;
    body = data ? JSON.stringify(data) : undefined;
    extraHeaders = cfgHeaders;
    signal = cfgSignal;
  }

  const headers: Record<string, string> = {
    "X-Correlation-ID": SESSION_CORRELATION_ID,
    ...extraHeaders,
  };
  if (body) {
    headers["Content-Type"] = headers["Content-Type"] ?? "application/json";
  }

  const initData = getTelegramInitData();
  if (initData) {
    headers["Authorization"] = `tma ${initData}`;
  } else {
    const devUserId = getDevUserId();
    if (devUserId) {
      headers["x-user-id"] = devUserId;
    }
  }

  const timeZone = getTimeZone();
  if (timeZone) {
    headers["X-Timezone"] = timeZone;
  }

  const response = await fetch(fullUrl, {
    method,
    headers,
    body,
    signal,
  });

  if (!response.ok) {
    const errorBody = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, errorBody.detail ?? "Request failed");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
