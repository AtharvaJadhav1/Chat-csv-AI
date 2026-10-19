"use client";

import { useRef, useState, type DragEvent } from "react";
import { FileUp, FlaskConical } from "lucide-react";
import { useApp } from "@/lib/AppContext";
import { ErrorBanner, PrivacyNote, Spinner } from "@/components/Common";

export default function UploadZone({ compact = false }: { compact?: boolean }) {
  const { upload, upload_file, load_sample, health, backendError } = useApp();
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const working = upload.status === "uploading" || upload.status === "processing";

  const pick = (files: FileList | null) => {
    const file = files?.[0];
    if (file) void upload_file(file);
    if (inputRef.current) inputRef.current.value = "";
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (!working) pick(e.dataTransfer.files);
  };

  return (
    <section className="card p-4 sm:p-5">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`flex flex-col items-center gap-3 rounded-xl border-2 border-dashed text-center transition ${
          compact ? "px-4 py-5" : "px-4 py-10"
        } ${dragging ? "border-brand bg-brand/5" : "border-border"}`}
      >
        <span className="flex h-11 w-11 items-center justify-center rounded-full bg-brand/10 text-brand">
          {working ? <Spinner className="h-5 w-5" /> : <FileUp className="h-5 w-5" />}
        </span>
        {working ? (
          <div className="w-full max-w-sm">
            <p className="text-sm font-medium">{upload.status === "uploading" ? `Uploading… ${upload.progress}%` : "Validating and profiling your dataset…"}</p>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-subtle" role="progressbar" aria-valuenow={upload.progress} aria-valuemin={0} aria-valuemax={100}>
              <div className="h-full rounded-full bg-brand transition-all" style={{ width: `${upload.status === "processing" ? 100 : upload.progress}%` }} />
            </div>
          </div>
        ) : (
          <>
            <div>
              <p className="font-medium">{compact ? "Upload a different CSV" : "Drag and drop your CSV here"}</p>
              <p className="mt-0.5 text-sm text-muted">
                .csv files up to {health?.max_file_size_mb ?? 25} MB and {(health?.max_rows ?? 100000).toLocaleString()} rows
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              <button className="btn-primary" onClick={() => inputRef.current?.click()}>
                Browse file
              </button>
              <button className="btn-ghost" onClick={() => void load_sample("students.csv")}>
                <FlaskConical className="h-4 w-4" /> Try sample students.csv
              </button>
              <button className="btn-ghost" onClick={() => void load_sample("sales.csv")}>
                <FlaskConical className="h-4 w-4" /> Try sample sales.csv
              </button>
            </div>
          </>
        )}
        <input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => pick(e.target.files)} aria-label="Choose CSV file" />
      </div>
      {upload.status === "error" && upload.error && <div className="mt-3"><ErrorBanner message={upload.error} /></div>}
      {backendError && <div className="mt-3"><ErrorBanner message={backendError} /></div>}
      <div className="mt-4">
        <PrivacyNote />
      </div>
    </section>
  );
}
