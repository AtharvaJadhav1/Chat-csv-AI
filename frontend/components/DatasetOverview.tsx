"use client";

import { usePathname, useRouter } from "next/navigation";
import { MousePointerClick, Sparkles, Trash2 } from "lucide-react";
import { useApp } from "@/lib/AppContext";
import type { ColumnKind } from "@/types";
import { Spinner } from "@/components/Common";

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="lift rounded-lg border border-border bg-subtle/60 px-3.5 py-3">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-0.5 text-xl font-semibold">{value}</p>
    </div>
  );
}

function questionFor(kind: ColumnKind, name: string): string {
  if (kind === "numeric") return `Show the distribution of ${name}`;
  if (kind === "datetime") return `Show the number of rows by month`;
  return `Show the number of rows by ${name}`;
}

function ColumnChips({ label, names, kind, onPick }: { label: string; names: string[]; kind: ColumnKind; onPick: (q: string) => void }) {
  if (!names.length) return null;
  return (
    <div>
      <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        {names.map((n) => (
          <button key={n} className="chip cursor-pointer transition hover:border-brand hover:bg-brand/10 hover:text-brand" title={`Ask about ${n}`} onClick={() => onPick(questionFor(kind, n))}>
            {n}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function DatasetOverview({ onAnalyze }: { onAnalyze?: () => void }) {
  const { dataset, insights, analyze, remove_dataset, datasetTheme, set_draft } = useApp();
  const router = useRouter();
  const pathname = usePathname();
  if (!dataset) return null;
  const p = dataset.profile;
  const ThemeIcon = datasetTheme.icon;

  const askAbout = (question: string) => {
    set_draft(question);
    if (pathname !== "/" && pathname !== "/chat") router.push("/chat");
    else document.getElementById("chat-panel")?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  return (
    <section className="card animate-fade-up overflow-hidden p-4 sm:p-5" style={{ backgroundImage: "linear-gradient(135deg, rgb(var(--brand) / 0.10), transparent 45%)" }}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-brand text-brand-fg shadow-card">
            <ThemeIcon className="h-6 w-6" />
          </span>
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-wide text-brand">{datasetTheme.label} detected</p>
            <h2 className="truncate text-lg font-semibold">{p.filename}</h2>
            <p className="text-sm text-muted">{p.rows.toLocaleString()} rows × {p.columns} columns</p>
          </div>
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
        <ColumnChips label="Numeric columns" names={p.numeric_columns} kind="numeric" onPick={askAbout} />
        <ColumnChips label="Categorical columns" names={p.categorical_columns} kind="categorical" onPick={askAbout} />
        <ColumnChips label="Date columns" names={p.datetime_columns} kind="datetime" onPick={askAbout} />
        <ColumnChips label="Boolean columns" names={p.boolean_columns} kind="boolean" onPick={askAbout} />
      </div>
      <p className="mt-3 flex items-center gap-1.5 text-xs text-muted">
        <MousePointerClick className="h-3.5 w-3.5" /> Click any column to ask about it.
      </p>

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
