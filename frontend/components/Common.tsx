"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { AlertTriangle, ShieldCheck, Upload } from "lucide-react";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function EmptyState({ title, text }: { title: string; text: string }) {
  return (
    <div className="card flex flex-col items-center gap-3 px-6 py-14 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-brand/10 text-brand">
        <Upload className="h-5 w-5" />
      </span>
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="max-w-md text-sm text-muted">{text}</p>
      <Link href="/" className="btn-primary mt-1">
        Upload a CSV
      </Link>
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div role="alert" className="flex items-start gap-2.5 rounded-lg border border-danger/30 bg-danger/10 px-3.5 py-3 text-sm text-danger">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <span className="whitespace-pre-line">{message}</span>
    </div>
  );
}

export function PrivacyNote() {
  return (
    <p className="flex items-start gap-2 text-xs text-muted">
      <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ok" />
      <span>
        Your CSV stays private: it is held in server memory only (never saved to disk or logs) and deleted after inactivity.
        Only column names, summary statistics and a few example values are shared with the AI model, never your full data.
      </span>
    </p>
  );
}

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return <span className={`inline-block animate-spin rounded-full border-2 border-current border-t-transparent ${className}`} aria-hidden />;
}
