"use client";

import { useCallback, useEffect, useState } from "react";

export const ADVANCED_MODE_KEY = "FP_ADVANCED_MODE";
const ADVANCED_MODE_EVENT = "fp-advanced-mode-change";

export function isAdvancedModeEnabled(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(ADVANCED_MODE_KEY) === "true";
}

export function setAdvancedModeEnabled(value: boolean) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ADVANCED_MODE_KEY, value ? "true" : "false");
  window.dispatchEvent(new CustomEvent(ADVANCED_MODE_EVENT, { detail: value }));
}

export function useAdvancedMode() {
  const [enabled, setEnabledState] = useState(false);

  useEffect(() => {
    setEnabledState(isAdvancedModeEnabled());

    const sync = () => setEnabledState(isAdvancedModeEnabled());
    window.addEventListener("storage", sync);
    window.addEventListener(ADVANCED_MODE_EVENT, sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(ADVANCED_MODE_EVENT, sync);
    };
  }, []);

  const setEnabled = useCallback((value: boolean) => {
    setAdvancedModeEnabled(value);
    setEnabledState(value);
  }, []);

  return [enabled, setEnabled] as const;
}
