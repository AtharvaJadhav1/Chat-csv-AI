"use client";

import { useApp } from "@/lib/AppContext";
import { EmptyState, PageHeader } from "@/components/Common";
import DatasetOverview from "@/components/DatasetOverview";
import DataPreview from "@/components/DataPreview";
import UploadZone from "@/components/UploadZone";
import type { ColumnKind } from "@/types";

const f = (n: number | null | undefined) => (n === null || n === undefined ? "—" : Number.isInteger(n) ? String(n) : n.toFixed(2));
const KIND_LABEL: Record<ColumnKind, string> = { numeric: "Numeric", categorical: "Categorical", datetime: "Date", boolean: "Boolean" };

export default function DatasetPage() {
  const { dataset } = useApp();
  if (!dataset) return (<><PageHeader title="Dataset" /><EmptyState title="No dataset yet" text="Upload a CSV to see its schema, statistics and a searchable preview." /></>);

  return (
    <div className="space-y-6">
      <PageHeader title="Dataset" subtitle="Schema, profile and preview of the uploaded file." />
      <DatasetOverview />
      <section className="card">
        <h2 className="border-b border-border p-4 font-semibold">Column profile</h2>
        <div className="scroll-thin overflow-x-auto">
          <table className="w-full min-w-max text-left text-sm">
            <thead className="bg-subtle/70">
              <tr>
                {["Column", "Type", "Missing", "Unique", "Mean", "Median", "Min", "Max", "Std dev", "Most common"].map((h) => (
                  <th key={h} className="whitespace-nowrap px-4 py-2.5 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {dataset.profile.column_profiles.map((c) => (
                <tr key={c.name} className="border-t border-border">
                  <td className="whitespace-nowrap px-4 py-2 font-medium">{c.name}{c.is_identifier && <span className="chip ml-2">id</span>}</td>
                  <td className="px-4 py-2">{KIND_LABEL[c.kind]}</td>
                  <td className="px-4 py-2 tabular-nums">{c.missing} <span className="text-muted">({c.missing_pct}%)</span></td>
                  <td className="px-4 py-2 tabular-nums">{c.unique}</td>
                  <td className="px-4 py-2 tabular-nums">{f(c.stats?.mean)}</td>
                  <td className="px-4 py-2 tabular-nums">{f(c.stats?.median)}</td>
                  <td className="px-4 py-2 tabular-nums">{f(c.stats?.min)}</td>
                  <td className="px-4 py-2 tabular-nums">{f(c.stats?.max)}</td>
                  <td className="px-4 py-2 tabular-nums">{f(c.stats?.std)}</td>
                  <td className="whitespace-nowrap px-4 py-2">{c.top_values.slice(0, 3).map((v) => `${v.value} (${v.count})`).join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <DataPreview />
      <UploadZone compact />
    </div>
  );
}
