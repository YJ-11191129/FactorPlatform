export type StrategyParamSchemaItem = {
  type?: "int" | "float" | "number" | "string" | "bool";
  default?: unknown;
  min?: number;
  max?: number;
};

export type StrategyInfo = {
  strategy_id: string;
  strategy_name: string;
  description: string;
  version: string;
  owner: string;
  parameter_schema: Record<string, StrategyParamSchemaItem>;
  python_entry: string;
};

