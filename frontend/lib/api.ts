import type { ChatResponse, Health, Insight, Preview, Stage, UploadResponse } from "@/types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message: string, public status = 0) {
    super(message);
  }
}

const UNREACHABLE = `Cannot reach the ChatCSV AI backend at ${API_URL}. Is it running?`;

async function errorFrom(res: Response): Promise<ApiError> {
  let detail = `Request failed (HTTP ${res.status}).`;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") detail = body.detail;
    else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join("; ");
  } catch {
    /* keep default */
  }
  return new ApiError(detail, res.status);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError(UNREACHABLE);
  }
  if (!res.ok) throw await errorFrom(res);
  return res.json() as Promise<T>;
}

export const getHealth = () => request<Health>("/api/health");

export function uploadDataset(file: File, onProgress: (pct: number) => void): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/api/dataset/upload`);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((100 * e.loaded) / e.total));
    xhr.onerror = () => reject(new ApiError(UNREACHABLE));
    xhr.onload = () => {
      let body: any = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* ignore */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as UploadResponse);
      else reject(new ApiError(typeof body?.detail === "string" ? body.detail : `Upload failed (HTTP ${xhr.status}).`, xhr.status));
    };
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

export const getPreview = (id: string, page: number, pageSize: number, search: string) =>
  request<Preview>(`/api/dataset/${id}/preview?page=${page}&page_size=${pageSize}&search=${encodeURIComponent(search)}`);

export const getInsights = (id: string) =>
  request<{ insights: Insight[] }>(`/api/dataset/${id}/insights`, { method: "POST" }).then((r) => r.insights);

export const deleteDataset = (id: string) => request(`/api/dataset/${id}`, { method: "DELETE" }).catch(() => undefined);
export const clearServerHistory = (id: string) => request(`/api/dataset/${id}/history`, { method: "DELETE" }).catch(() => undefined);

/** Streams real pipeline stages (NDJSON), resolving with the final result. */
export async function streamChat(id: string, question: string, onStage: (s: Stage) => void): Promise<ChatResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset_id: id, question }),
    });
  } catch {
    throw new ApiError(UNREACHABLE);
  }
  if (!res.ok || !res.body) throw await errorFrom(res);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: ChatResponse | null = null;
  const handle = (line: string) => {
    if (!line.trim()) return;
    const event = JSON.parse(line);
    if (event.stage) onStage(event.stage as Stage);
    if (event.result) result = event.result as ChatResponse;
  };
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    lines.forEach(handle);
  }
  handle(buffer);
  if (!result) throw new ApiError("The server closed the connection before sending a result.");
  return result;
}
