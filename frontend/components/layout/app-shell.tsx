"use client";

// Application shell — the responsive grid composing every layout
// region, wrapped in ChatProvider so the chat area, sidebar (system
// messages), and right panel (recent sources) share one live
// conversation. Desktop anatomy:
//
//   ┌──────────┬──────────────────────────────┐
//   │          │ Top navigation               │
//   │ Sidebar  ├──────────────────┬───────────┤
//   │ (280px,  │ Main chat area   │ Right     │
//   │  md+)    │ (fluid)          │ panel     │
//   │          │                  │ (xl+)     │
//   │          ├──────────────────┴───────────┤
//   │          │ Bottom status bar            │
//   └──────────┴──────────────────────────────┘

import { ChatArea } from "@/components/chat/chat-area";
import { RightPanel } from "@/components/layout/right-panel";
import { StatusBar } from "@/components/layout/status-bar";
import { TopNav } from "@/components/layout/top-nav";
import { Sidebar } from "@/components/sidebar/sidebar";
import { ChatProvider } from "@/hooks/useChat";

export function AppShell() {
  return (
    <ChatProvider>
      <div className="flex h-dvh overflow-hidden bg-background text-foreground">
        <div className="hidden md:block">
          <Sidebar />
        </div>

        <div className="flex min-w-0 flex-1 flex-col">
          <TopNav />

          <div className="flex min-h-0 flex-1">
            <ChatArea />
            <div className="hidden xl:block">
              <RightPanel />
            </div>
          </div>

          <StatusBar />
        </div>
      </div>
    </ChatProvider>
  );
}
