// Tests for the shared confirmToast helper: it must raise a warning
// toast carrying the title, description, and a single action button
// whose click runs the caller's onConfirm (and NOT before).

import { toast } from "sonner";
import { describe, expect, it, vi } from "vitest";

import { confirmToast } from "@/lib/confirm-toast";

vi.mock("sonner", () => ({
  toast: { warning: vi.fn() },
}));

describe("confirmToast", () => {
  it("raises a warning toast with the title, description, and action", () => {
    const onConfirm = vi.fn();
    confirmToast({
      title: "Delete report.pdf?",
      description: "This removes it permanently.",
      actionLabel: "Delete",
      onConfirm,
    });

    expect(toast.warning).toHaveBeenCalledWith("Delete report.pdf?", {
      description: "This removes it permanently.",
      action: { label: "Delete", onClick: onConfirm },
    });
    // The action must be armed, not fired, until the user clicks it.
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("defaults the action label to Confirm when none is given", () => {
    confirmToast({ title: "Sure?", description: "…", onConfirm: () => {} });

    const [, options] = vi.mocked(toast.warning).mock.calls.at(-1)!;
    expect(options?.action).toMatchObject({ label: "Confirm" });
  });
});
