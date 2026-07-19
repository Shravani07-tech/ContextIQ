// Home page — renders the application shell, now backed by live
// FastAPI data (the ?demo=1 placeholder mode is gone; real data
// replaced it in Phase 3A).

import { AppShell } from "@/components/layout/app-shell";

export default function Home() {
  return <AppShell />;
}
