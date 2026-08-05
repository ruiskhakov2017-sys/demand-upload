import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { App } from "./app/App";
import { AppErrorBoundary } from "./app/AppErrorBoundary";
import { ThemePreferenceProvider } from "./app/ThemePreference";
import { LocaleProvider } from "./i18n";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false
    }
  }
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <LocaleProvider>
        <ThemePreferenceProvider>
          <AppErrorBoundary>
            <App />
          </AppErrorBoundary>
        </ThemePreferenceProvider>
      </LocaleProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
