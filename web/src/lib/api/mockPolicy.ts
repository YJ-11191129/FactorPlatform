export function allowMockFallback(): boolean {
  const raw = process.env.NEXT_PUBLIC_ALLOW_MOCK_FALLBACK;
  if (!raw) return false;
  return !["0", "false", "no", "off"].includes(raw.toLowerCase());
}

export function mockModeLabel(): "demo" | "production" {
  return allowMockFallback() ? "demo" : "production";
}

export function mockFallbackError(feature: string): Error {
  return new Error(`${feature} mock fallback is disabled. Set NEXT_PUBLIC_ALLOW_MOCK_FALLBACK=1 for demo mode.`);
}
