import type {
  AnalysisReport,
  AnalyzeRequest,
  ExportFormat,
  ExtractResponse,
  HealthResponse,
  ModelStatus,
  StreamEvent,
} from "../types";

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

const UNREACHABLE =
  "Can't reach the MeetingMind API. Make sure the backend is running (scripts/start-backend) on port 8000.";

async function request(path: string, init?: RequestInit): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(UNREACHABLE, 0);
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      if (res.status === 502 || res.status === 504) detail = UNREACHABLE;
    }
    throw new ApiError(detail, res.status);
  }
  return res;
}

export const api = {
  async health(): Promise<HealthResponse> {
    return (await request("/api/health")).json();
  },

  async warmup(): Promise<ModelStatus[]> {
    return (await request("/api/models/warmup", { method: "POST" })).json();
  },

  async extract(file: File): Promise<ExtractResponse> {
    const form = new FormData();
    form.append("file", file);
    return (await request("/api/extract", { method: "POST", body: form })).json();
  },

  /** Streams real pipeline progress events (NDJSON) and resolves when the stream ends. */
  async analyzeStream(body: AnalyzeRequest, onEvent: (e: StreamEvent) => void, signal?: AbortSignal): Promise<void> {
    const res = await request("/api/analyze/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
    if (!res.body) throw new ApiError("The browser does not support streaming responses.", 0);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let newline: number;
      while ((newline = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, newline).trim();
        buffer = buffer.slice(newline + 1);
        if (line) onEvent(JSON.parse(line) as StreamEvent);
      }
    }
    if (buffer.trim()) onEvent(JSON.parse(buffer) as StreamEvent);
  },

  /** Renders the current (possibly edited) report on the server and downloads the file. */
  async exportReport(format: ExportFormat, report: AnalysisReport): Promise<void> {
    const res = await request(`/api/export/${format}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(report),
    });
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") ?? "";
    const match = /filename="([^"]+)"/.exec(disposition);
    const ext = { json: "json", csv: "csv", markdown: "md", pdf: "pdf" }[format];
    const filename = match?.[1] ?? `MeetingMind_report.${ext}`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
};
