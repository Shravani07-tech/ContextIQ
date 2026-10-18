"use client";

// Close a hand-rolled popover/menu on outside pointer-down or Escape,
// returning focus to its trigger on Escape so keyboard users aren't
// stranded. Used by the export menu and the document-scope selector.

import { type RefObject, useEffect } from "react";

export function useDismissable(
  containerRef: RefObject<HTMLElement | null>,
  open: boolean,
  onClose: () => void,
  triggerRef?: RefObject<HTMLElement | null>,
): void {
  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: PointerEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) onClose();
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
        triggerRef?.current?.focus();
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [containerRef, open, onClose, triggerRef]);
}
