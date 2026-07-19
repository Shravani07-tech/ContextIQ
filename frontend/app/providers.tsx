"use client";

// App-wide client providers, kept in one place so layout.tsx (a
// server component) stays clean. TanStack Query owns all server
// state — API calls to the FastAPI backend will live in hooks that
// build on this client.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export default function Providers({ children }: { children: React.ReactNode }) {
  // useState (not a module global) so each browser session gets its
  // own client and nothing leaks between server-rendered requests.
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Local single-user API: retrying aggressively just delays
            // honest error states (e.g. "Ollama is down").
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
