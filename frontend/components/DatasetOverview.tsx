"use client";

import { Sparkles, Trash2 } from "lucide-react";
import { useApp } from "@/lib/AppContext";
import { Spinner } from "@/components/Common";

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-border bg-subtle/60 px-3.5 py-3">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-0.5 text-xl font-semibold">{value}</p>
    </div>
  );
}

function ColumnChips({ label, names }: { label: string; names: string[] }) {
  if (!names.length) return null;
  return (
    <div>
      <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        {names.map((n) => (
          <span key={n} className="chip">{n}</span>
        ))}
      </div>
    </div>
  );
}

export default function DatasetOverview({ onAnalyze }: { onAnalyze?: () => void }) {
  const { dataset, insights, analyze, remove_dataset } = useApp();
  if (!dataset) return null;
  const p = dataset.profile;

  return (
    <section className="card p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-muted">Dataset overview</p>
          <h2 className="truncate text-lg font-semibold">{p.filename}</h2>
          <p className="text-sm text-muted">{p.rows.toLocaleString()} rows × {p.columns} columns</p>
        </div>
        <div className="flex gap-2">
          <button
            className="btn-primary"
            disabled={insights.status === "loading"}
            onClick={() => {
              void analyze();
              onAnalyze?.();
            }}
          >
            {insights.status === "loading" ? <Spinner /> : <Sparkles className="h-4 w-4" />} Analyze Dataset
          </button>
          <button className="btn-ghost !px-2.5" onClick={() => void remove_dataset()} aria-label="Remove dataset" title="Remove dataset from memory">
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Rows" value={p.rows.toLocaleString()} />
        <Stat label="Columns" value={p.columns} />
        <Stat label="Missing values" value={p.missing_total.toLocaleString()} />
        <Stat label="Duplicate rows" value={p.duplicate_rows.toLocaleString()} />
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <ColumnChips label="Numeric columns" names={p.numeric_columns} />
        <ColumnChips label="Categorical columns" names={p.categorical_columns} />
        <ColumnChips label="Date columns" names={p.datetime_columns} />
        <ColumnChips label="Boolean columns" names={p.boolean_columns} />
      </div>

      {dataset.warnings.length > 0 && (
        <ul className="mt-4 space-y-1 rounded-lg border border-warn/30 bg-warn/10 px-3.5 py-2.5 text-sm text-warn">
          {dataset.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
