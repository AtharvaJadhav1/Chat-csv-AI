"use client";

import { useEffect, useState } from "react";
import { Calendar, ChevronLeft, ChevronRight, Hash, Search, ToggleLeft, Type } from "lucide-react";
import { getPreview } from "@/lib/api";
import { useApp } from "@/lib/AppContext";
import type { ColumnKind, Preview } from "@/types";
import { ErrorBanner } from "@/components/Common";

const KIND_ICON: Record<ColumnKind, typeof Hash> = { numeric: Hash, categorical: Type, datetime: Calendar, boolean: ToggleLeft };
const PAGE_SIZE = 15;

export default function DataPreview() {
  const { dataset } = useApp();
  const [preview, setPreview] = useState<Preview | null>(dataset?.firstPage ?? null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => {
      setQuery(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    if (!dataset) return;
    let cancelled = false;
    setLoading(true);
    getPreview(dataset.id, page, PAGE_SIZE, query)
      .then((p) => !cancelled && (setPreview(p), setError(null)))
      .catch((e: Error) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [dataset, page, query]);

  if (!dataset || !preview) return null;

  return (
    <section className="card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
        <div>
          <h2 className="font-semibold">Dataset preview</h2>
          <p className="text-xs text-muted">{preview.total_rows.toLocaleString()} matching rows</p>
        </div>
        <label className="relative w-full sm:w-64">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search all rows…"
            className="w-full rounded-lg border border-border bg-surface py-2 pl-8 pr-3 text-sm outline-none focus:ring-2 focus:ring-brand/40"
            aria-label="Search dataset rows"
          />
        </label>
      </div>
      {error && <div className="p-4"><ErrorBanner message={error} /></div>}
      <div className={`scroll-thin overflow-x-auto ${loading ? "opacity-60" : ""}`}>
        <table className="w-full min-w-max text-left text-sm">
          <thead className="bg-subtle/70">
            <tr>
              {preview.columns.map((c) => {
                const Icon = KIND_ICON[preview.kinds[c]] ?? Type;
                return (
                  <th key={c} className="whitespace-nowrap px-4 py-2.5 font-medium">
                    <span className="inline-flex items-center gap-1.5">
                      <Icon className="h-3.5 w-3.5 text-muted" aria-label={preview.kinds[c]} />
                      {c}
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {preview.rows.map((row, i) => (
              <tr key={i} className="border-t border-border hover:bg-subtle/40">
                {row.map((cell, j) => (
                  <td key={j} className={`whitespace-nowrap px-4 py-2 ${preview.kinds[preview.columns[j]] === "numeric" ? "text-right tabular-nums" : ""}`}>
                    {cell === null ? <span className="text-muted">—</span> : String(cell)}
                  </td>
                ))}
              </tr>
            ))}
            {preview.rows.length === 0 && (
              <tr>
                <td colSpan={preview.columns.length} className="px-4 py-8 text-center text-muted">No rows match your search.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-border px-4 py-3 text-sm">
        <span className="text-muted">Page {preview.page} of {preview.total_pages}</span>
        <div className="flex gap-2">
          <button className="btn-ghost !px-2.5" disabled={preview.page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Previous page">
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button className="btn-ghost !px-2.5" disabled={preview.page >= preview.total_pages} onClick={() => setPage((p) => p + 1)} aria-label="Next page">
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </section>
  );
}
