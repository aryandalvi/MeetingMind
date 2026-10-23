import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { useWorkspace, WorkspaceProvider } from "../state/workspace";
import { Results, SECTIONS } from "../pages/Results";
import type { AnalysisReport } from "../types";
import fixture from "./fixture_report.json";

const report = fixture as unknown as AnalysisReport;

beforeAll(() => {
  // Recharts' ResponsiveContainer needs ResizeObserver; jsdom lacks dialog methods.
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
afterEach(cleanup);

let workspace: ReturnType<typeof useWorkspace>;
function Capture() {
  workspace = useWorkspace();
  return null;
}

function renderAt(path: string) {
  return render(
    <WorkspaceProvider initialReport={report}>
      <Capture />
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/results/:section?" element={<Results />} />
          <Route path="/new" element={<div>new page</div>} />
        </Routes>
      </MemoryRouter>
    </WorkspaceProvider>,
  );
}

describe("Results page", () => {
  it.each(SECTIONS.map((s) => s.key))("renders the %s section", async (key) => {
    renderAt(key === "overview" ? "/results" : `/results/${key}`);
    expect(await screen.findByText(report.meeting.title)).toBeTruthy();
  });

  it("edits to an action item update the report used for exports", async () => {
    renderAt("/results/actions");
    await screen.findByText(report.meeting.title);
    const owner = screen.getAllByLabelText("Owner")[0] as HTMLInputElement;
    await act(async () => {
      fireEvent.change(owner, { target: { value: "Zoë Example" } });
      fireEvent.blur(owner);
    });
    const status = screen.getAllByLabelText("Status")[0] as HTMLSelectElement;
    await act(async () => {
      fireEvent.change(status, { target: { value: "done" } });
    });
    const edited = workspace.report!.action_items[0];
    expect(edited.owner).toBe("Zoë Example");
    expect(edited.owner_source).toBe("user");
    expect(edited.status).toBe("done");
    expect(edited.edited).toBe(true);
    expect(workspace.report!.edited_at).toBeTruthy();
  });
});
