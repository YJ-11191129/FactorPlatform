import type { FactorDetail, FactorFrequency, FactorItem } from "@/types/factor";

export type BackendFactorInfo = {
  factor_name: string;
  display_name?: string;
  category?: string;
  description?: string;
  version?: string;
  dependencies?: string[];
  parameter_schema?: Record<string, unknown>;
};

function normalizeFrequency(version?: string): FactorFrequency {
  if (version && version.toUpperCase().includes("_W_")) return "weekly";
  if (version && version.toUpperCase().includes("_M_")) return "monthly";
  return "daily";
}

export function adaptFactorItem(raw: BackendFactorInfo): FactorItem {
  const factorName = raw.factor_name;
  return {
    factor_id: factorName,
    factor_name: factorName,
    display_name: raw.display_name || factorName,
    category: raw.category || "UNKNOWN",
    tags: [],
    frequency: normalizeFrequency(raw.version),
    market_scope: ["CN-A"],
    direction: "unknown",
    status: "research",
    owner: "",
    version: raw.version || "",
  };
}

export function adaptFactorDetail(raw: BackendFactorInfo): FactorDetail {
  const base = adaptFactorItem(raw);
  return {
    ...base,
    description: raw.description || "",
    formula: "",
    data_source: ["qlib_bin"],
    neutralization: ["industry", "mktcap"],
    winsorize: "MAD 5x",
    standardize: "cross-sectional z-score",
    dependencies: raw.dependencies || [],
    code_snippet: "",
    diagnostics: {},
  };
}

