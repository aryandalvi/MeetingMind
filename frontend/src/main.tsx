import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "@fontsource-variable/inter";
import "@fontsource-variable/plus-jakarta-sans";
import "@fontsource-variable/jetbrains-mono";
import "./index.css";
import { Layout } from "./components/Layout";
import { WorkspaceProvider } from "./state/workspace";
import { Dashboard } from "./pages/Dashboard";
import { NewAnalysis } from "./pages/NewAnalysis";
import { Processing } from "./pages/Processing";

const Results = lazy(() => import("./pages/Results").then((m) => ({ default: m.Results })));

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <WorkspaceProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="new" element={<NewAnalysis />} />
            <Route path="processing" element={<Processing />} />
            <Route
              path="results/:section?"
              element={
                <Suspense fallback={<div className="p-10 text-center text-sm text-muted">Loading report…</div>}>
                  <Results />
                </Suspense>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </WorkspaceProvider>
  </StrictMode>,
);
