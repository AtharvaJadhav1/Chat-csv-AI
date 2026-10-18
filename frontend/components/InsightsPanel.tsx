"use client";

import { AlertCircle, BarChart3, CheckCircle2, GitCompare, Info, Sparkles, TrendingUp, Zap } from "lucide-react";
import { useApp } from "@/lib/AppContext";
import { ErrorBanner, Spinner } from "@/components/Common";

const ICONS: Record<string, typeof Info> = {
  overview: Info,
  quality: AlertCircle,
  comparison: GitCompare,
  distribution: BarChart3,
  correlation: TrendingUp,
  outliers: Zap,
};

export default function InsightsPanel() {
  const { insights, analyze, dataset } = useApp();
  if (!dataset) return null;

  return (
    <section className="card p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 font-semibold">
            <Sparkles className="h-4 w-4 text-brand" /> AI Dataset Insights
          </h2>
          <p className="text-xs text-muted">Every insight is calculated directly from your data. Nothing is estimated or invented.</p>
        </div>
        <button className="btn-ghost" onClick={() => void analyze()} disabled={insights.status === "loading"}>
          {insights.status === "loading" ? <Spinner /> : <Sparkles className="h-4 w-4" />}
          {insights.status === "done" ? "Re-analyze" : "Analyze Dataset"}
        </button>
      </div>

      {insights.status === "loading" && (
        <p className="mt-4 flex items-center gap-2 text-sm text-muted" role="status"><Spinner /> Analyzing your dataset...</p>
      )}
      {insights.status === "error" && <div className="mt-4"><ErrorBanner message={insights.error ?? "Could not generate insights."} /></div>}
      {insights.status === "idle" && <p className="mt-4 text-sm text-muted">Click “Analyze Dataset” to generate automatic insights: category leaders, missing data, correlations and outliers.</p>}
      {insights.status === "done" && (
        <ol className="mt-4 space-y-2.5">
          {insights.items.map((item, i) => {
            const Icon = ICONS[item.category] ?? CheckCircle2;
            return (
              <li key={i} className="flex gap-3 rounded-lg border border-border bg-subtle/40 px-3.5 py-3">
                <Icon className="mt-0.5 h-4 w-4 shrink-0 text-brand" />
                <div>
                  <p className="text-sm font-medium">{item.title}</p>
                  <p className="text-sm text-muted">{item.detail}</p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
