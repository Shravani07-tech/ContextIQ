import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// Unmount + clear DOM between tests so state (and sessionStorage
// writes triggered by unmount effects) never leaks across cases.
afterEach(() => {
  cleanup();
  sessionStorage.clear();
});

// jsdom doesn't implement scrollIntoView; MessageList calls it on
// every render for auto-scroll, so tests need a harmless stand-in.
Element.prototype.scrollIntoView = vi.fn();

// crypto.randomUUID is used by useChat to key messages; Node's test
// environment under jsdom doesn't always expose it on `crypto`.
if (!globalThis.crypto?.randomUUID) {
  Object.defineProperty(globalThis, "crypto", {
    value: { ...globalThis.crypto, randomUUID: () => Math.random().toString(36).slice(2) },
  });
}
