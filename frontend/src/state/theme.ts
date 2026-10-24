import { useEffect, useState } from "react";

export type Theme = "dark" | "light";

const KEY = "meetingmind-theme";

function stored(): Theme | null {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null; // private browsing / blocked storage
  }
}

// The first paint's theme is set synchronously by an inline script in index.html (before any
// CSS applies), so there's never a flash; this hook just reads that choice and keeps it in sync.
export function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(() => (document.documentElement.dataset.theme as Theme) ?? "dark");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      // ignore — theme just won't persist across reloads
    }
  }, [theme]);

  // Follow the OS if the person hasn't explicitly chosen a theme in this browser.
  useEffect(() => {
    if (stored()) return;
    const mql = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = (e: MediaQueryListEvent) => setTheme(e.matches ? "light" : "dark");
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  return [theme, setTheme];
}
