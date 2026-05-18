export type ApiError = {
  message: string;
  status?: number;
  detail?: unknown;
};

const DEFAULT_BASE_PATH = "/backend";

export function apiBasePath(): string {
  return process.env.NEXT_PUBLIC_API_BASE_PATH || DEFAULT_BASE_PATH;
}

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const base = apiBasePath();
  const url = `${base}${path}`;
  const apiKey =
    process.env.NEXT_PUBLIC_API_KEY ||
    (typeof window !== "undefined" ? window.localStorage.getItem("FP_API_KEY") || "" : "");

  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(apiKey ? { "X-API-Key": apiKey } : {}),
        ...(init?.headers || {}),
      },
      cache: "no-store",
    });
  } catch (e) {
    throw { message: "Network request failed", detail: e } satisfies ApiError;
  }

  const contentType = res.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const body = isJson ? await res.json().catch(() => null) : await res.text().catch(() => null);

  if (!res.ok) {
    const msg = body && typeof body === "object" && "detail" in body ? String((body as any).detail) : `HTTP ${res.status}`;
    throw { message: msg, status: res.status, detail: body } satisfies ApiError;
  }

  return body as T;
}
