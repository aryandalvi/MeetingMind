import { useEffect, type ReactNode } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { useWorkspace, WorkspaceProvider } from "../state/workspace";
import { Processing } from "../pages/Processing";
import { api } from "../api/client";
import type { AnalysisReport, StreamEvent } from "../types";
import fixture from "./fixture_report.json";

beforeAll(() => {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

/** Starts a job, then mounts the router (in the app the job always exists before /processing). */
function Start({ children }: { children: ReactNode }) {
  const { startJob, job, report } = useWorkspace();
  useEffect(() => {
    startJob({ transcript: "Ann: hello there everyone, let's start.", title: "T", meeting_date: null, context: null });
  }, [startJob]);
  return job || report ? <>{children}</> : null;
}

function ResultsStub() {
  const { report } = useWorkspace();
  return <div>results for {report?.meeting.title}</div>;
}

describe("Processing page", () => {
  it("shows real stages and hands the report to the results page", async () => {
    const stream = vi.spyOn(api, "analyzeStream").mockImplementation(async (_req, onEvent: (e: StreamEvent) => void) => {
      onEvent({ type: "accepted", stages: [{ key: "models", label: "Loading NLP models" }] });
      onEvent({ type: "stage", stage: "models", label: "Loading NLP models", status: "started" });
      await new Promise((r) => setTimeout(r, 20));
      onEvent({ type: "stage", stage: "models", label: "Loading NLP models", status: "completed", elapsed_ms: 12 });
      onEvent({ type: "result", report: fixture as unknown as AnalysisReport });
    });
    render(
      <WorkspaceProvider>
        <Start>
          <MemoryRouter initialEntries={["/processing"]}>
            <Routes>
              <Route path="/processing" element={<Processing />} />
              <Route path="/results" element={<ResultsStub />} />
              <Route path="/new" element={<div>new page</div>} />
            </Routes>
          </MemoryRouter>
        </Start>
      </WorkspaceProvider>,
    );
    expect(await screen.findByText(/results for Mobile App Launch Sync/, {}, { timeout: 3000 })).toBeTruthy();
    expect(stream).toHaveBeenCalledTimes(1);
  });

  it("shows the server's error message", async () => {
    vi.spyOn(api, "analyzeStream").mockImplementation(async (_req, onEvent: (e: StreamEvent) => void) => {
      onEvent({ type: "accepted", stages: [{ key: "models", label: "Loading NLP models" }] });
      onEvent({ type: "error", code: "internal", message: "Analysis failed: OSError" });
    });
    render(
      <WorkspaceProvider>
        <Start>
          <MemoryRouter initialEntries={["/processing"]}>
            <Routes>
              <Route path="/processing" element={<Processing />} />
            </Routes>
          </MemoryRouter>
        </Start>
      </WorkspaceProvider>,
    );
    expect(await screen.findByText("Analysis failed: OSError")).toBeTruthy();
    expect(screen.getByText("Try again")).toBeTruthy();
  });
});
