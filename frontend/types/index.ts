export type ColumnKind = "numeric" | "categorical" | "datetime" | "boolean";
export type CellValue = string | number | boolean | null;

export interface NumericStats {
  mean: number | null;
  median: number | null;
  min: number | null;
  max: number | null;
  std: number | null;
}

export interface ColumnProfile {
  name: string;
  kind: ColumnKind;
  dtype: string;
  missing: number;
  missing_pct: number;
  unique: number;
  is_identifier: boolean;
  stats: NumericStats | null;
  top_values: { value: CellValue; count: number }[];
}

export interface DatasetProfile {
  filename: string;
  rows: number;
  columns: number;
  missing_total: number;
  duplicate_rows: number;
  numeric_columns: string[];
  categorical_columns: string[];
  datetime_columns: string[];
  boolean_columns: string[];
  column_profiles: ColumnProfile[];
}

export interface Preview {
  columns: string[];
  kinds: Record<string, ColumnKind>;
  rows: CellValue[][];
  page: number;
  page_size: number;
  total_rows: number;
  total_pages: number;
}

export interface UploadResponse {
  dataset_id: string;
  profile: DatasetProfile;
  preview: Preview;
  warnings: string[];
}

export interface TableData {
  columns: string[];
  rows: CellValue[][];
  total_rows: number;
  truncated: boolean;
}

export type ChartType = "bar" | "line" | "pie" | "histogram" | "scatter" | "area";

export interface ChartSpec {
  type: ChartType;
  title: string;
  xAxis: string;
  yAxis: string;
  data: Record<string, string | number | null>[];
}

export interface ChatResponse {
  status: "ok" | "unsupported" | "clarification" | "error";
  answer: string;
  analysis: {
    intent: string;
    operation: string | null;
    column: string | null;
    explanation: string;
    plan: Record<string, unknown>;
  } | null;
  stat: { label: string; value: string } | null;
  table: TableData | null;
  chart: ChartSpec | null;
  planner: string;
  timestamp: string;
}

export type Stage = "analyzing" | "understanding" | "running" | "preparing";

export interface ChatMessage {
  id: string;
  question: string;
  askedAt: string;
  loading: boolean;
  stage: Stage;
  response?: ChatResponse;
}

export interface Insight {
  category: string;
  title: string;
  detail: string;
}

export interface Health {
  status: string;
  planner: "llm" | "rules";
  llm_model: string | null;
  max_file_size_mb: number;
  max_rows: number;
}
