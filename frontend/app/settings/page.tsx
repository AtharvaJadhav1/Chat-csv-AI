"use client";

import { Moon, Sun, Trash2 } from "lucide-react";
import { useApp } from "@/lib/AppContext";
import { ErrorBanner, PageHeader, PrivacyNote } from "@/components/Common";
import { API_URL } from "@/lib/api";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-4 py-3 text-sm first:border-t-0">
      <span className="text-muted">{label}</span>
      <span className="font-medium">{children}</span>
    </div>
  );
}

export default function SettingsPage() {
  const { theme, toggle_theme, health, backendError, dataset, remove_dataset } = useApp();
  return (
    <div className="space-y-6">
      <PageHeader title="Settings" subtitle="Appearance, backend status and privacy." />
      <section className="card">
        <h2 className="border-b border-border p-4 font-semibold">Appearance</h2>
        <Row label="Theme">
          <button className="btn-ghost" onClick={toggle_theme}>
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />} {theme === "dark" ? "Switch to light" : "Switch to dark"}
          </button>
        </Row>
      </section>

      <section className="card">
        <h2 className="border-b border-border p-4 font-semibold">Backend</h2>
        {backendError && <div className="p-4"><ErrorBanner message={backendError} /></div>}
        <Row label="API URL">{API_URL}</Row>
        {health && (
          <>
            <Row label="Question planner">{health.planner === "llm" ? `LLM (${health.llm_model})` : "Rule-based (set OPENAI_API_KEY to enable the LLM)"}</Row>
            <Row label="Max file size">{health.max_file_size_mb} MB</Row>
            <Row label="Max rows">{health.max_rows.toLocaleString()}</Row>
          </>
        )}
      </section>

      <section className="card space-y-3 p-4">
        <h2 className="font-semibold">Privacy</h2>
        <PrivacyNote />
        {dataset && (
          <button className="btn-ghost text-danger" onClick={() => void remove_dataset()}>
            <Trash2 className="h-4 w-4" /> Delete “{dataset.profile.filename}” from server memory
          </button>
        )}
      </section>
    </div>
  );
}
