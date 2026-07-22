// Shared "confirm a destructive action" toast — one warning toast with
// a single confirming action button. Previously this exact
// toast.warning(title, { description, action }) shape was duplicated in
// the sidebar (clear database), the document library (delete document),
// and the chat toolbar (clear conversation); centralizing it keeps the
// confirm UX identical everywhere and gives one place to evolve it.

import { toast } from "sonner";

export interface ConfirmToastOptions {
  /** Headline question, e.g. "Delete report.pdf?". */
  title: string;
  /** One-line consequence, shown beneath the title. */
  description: string;
  /** Label for the confirming action button (default "Confirm"). */
  actionLabel?: string;
  /** Run when the user presses the action button. */
  onConfirm: () => void;
}

export function confirmToast({
  title,
  description,
  actionLabel = "Confirm",
  onConfirm,
}: ConfirmToastOptions): void {
  toast.warning(title, {
    description,
    action: { label: actionLabel, onClick: onConfirm },
  });
}
