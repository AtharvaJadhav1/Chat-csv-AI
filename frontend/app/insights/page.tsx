"use client";

import { useEffect, useRef } from "react";
import { useApp } from "@/lib/AppContext";
import { EmptyState, PageHeader } from "@/components/Common";
import InsightsPanel from "@/components/InsightsPanel";

export default function InsightsPage() {
  const { dataset, insights, analyze } = useApp();
  const requested = useRef(false);

  useEffect(() => {
    if (dataset && insights.status === "idle" && !requested.current) {
      requested.current = true;
      void analyze();
    }
  }, [dataset, insights.status, analyze]);

  return (
    <div className="space-y-6">
      <PageHeader title="Insights" subtitle="Automatic findings computed from your dataset." />
      {dataset ? <InsightsPanel /> : <EmptyState title="No dataset to analyze" text="Upload a CSV and ChatCSV AI will surface category leaders, missing data, correlations and outliers." />}
    </div>
  );
}
