import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@fontsource-variable/inter";
import "./styles/fontawesome/all.min.css";
import { App } from "./app";
import { ErrorBoundary } from "./components/error-boundary";
import "./styles/globals.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element");

/*
 * A rebuilt renderer replaces its hashed chunks. A tab still running the old
 * index can then fail a lazy route import with "Failed to fetch dynamically
 * imported module". Reload once so the index and the chunks agree again; the
 * second failure (a genuinely missing file) reaches the error boundary.
 */
window.addEventListener("vite:preloadError", (event) => {
  event.preventDefault();
  const guard = "camxora:preload-reload";
  try {
    if (sessionStorage.getItem(guard) === "1") return;
    sessionStorage.setItem(guard, "1");
  } catch {
    // Storage can be unavailable; a single reload is still the right move.
  }
  window.location.reload();
});

createRoot(root).render(
  <StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
);
