// Tests for the shared InlineError card: it must announce itself to
// assistive tech (role="alert"), show the caller's message, and wire
// its Retry button to the provided handler.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { InlineError } from "@/components/shared/inline-error";

describe("InlineError", () => {
  it("renders the message inside an alert region", () => {
    render(<InlineError message="Couldn't load documents" onRetry={() => {}} />);

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Couldn't load documents");
  });

  it("calls onRetry when the Retry button is pressed", async () => {
    const onRetry = vi.fn();
    render(<InlineError message="Failed" onRetry={onRetry} />);

    await userEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
