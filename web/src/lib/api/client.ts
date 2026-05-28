export type ApiError = {
  message: string;
  status?: number;
  detail?: unknown;
};

type FetchJsonInit = RequestInit & {
  timeoutMs?: number;
};

const DEFAULT_BASE_PATH = "/backend";

export function apiBasePath(): string {
  return process.env.NEXT_PUBLIC_API_BASE_PATH || DEFAULT_BASE_PATH;
}

function effectiveApiKey(): string {
  const storedKey = typeof window !== "undefined" ? window.localStorage.getItem("FP_API_KEY")?.trim() || "" : "";
  return storedKey || process.env.NEXT_PUBLIC_API_KEY || "";
}

function detailMessage(detail: unknown): string | null {
  if (!detail) return null;
  if (typeof detail === "string") return detail;
  if (typeof detail !== "object") return null;
  if ("message" in detail && typeof (detail as any).message === "string") return (detail as any).message;
  if ("detail" in detail) return detailMessage((detail as any).detail);
  if ("error" in detail && typeof (detail as any).error === "string") return (detail as any).error;
  return null;
}

export async function fetchJson<T>(path: string, init?: FetchJsonInit): Promise<T> {
  const base = apiBasePath();
  const url = `${base}${path}`;
  const apiKey = effectiveApiKey();
  const timeoutMs = init?.timeoutMs;
  const controller = timeoutMs ? new AbortController() : null;
  const timeout = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;
  const { timeoutMs: _timeoutMs, signal: initSignal, ...requestInit } = init || {};

  if (initSignal && controller) {
    if (initSignal.aborted) controller.abort();
    else initSignal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  let res: Response;
  try {
    res = await fetch(url, {
      ...requestInit,
      signal: controller?.signal || initSignal,
      headers: {
        "Content-Type": "application/json",
        ...(apiKey ? { "X-API-Key": apiKey } : {}),
        ...(requestInit.headers || {}),
      },
      cache: "no-store",
    });
  } catch (e) {
    throw { message: "Network request failed", detail: e } satisfies ApiError;
  } finally {
    if (timeout) clearTimeout(timeout);
  }

  const contentType = res.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const body = isJson ? await res.json().catch(() => null) : await res.text().catch(() => null);

  if (!res.ok) {
    const msg = detailMessage(body) || `HTTP ${res.status}`;
    throw { message: msg, status: res.status, detail: body } satisfies ApiError;
  }

  return body as T;
}
