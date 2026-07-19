"use client";

// Route-transition template: every page entry fades in with a tiny
// rise — 180ms ease-out, inside the design system's 150–200ms motion
// budget (DESIGN.md §14). Skipped entirely for users who prefer
// reduced motion. With one route today this fires on first load;
// future routes inherit the same entrance for free.

import { motion, useReducedMotion } from "framer-motion";

export default function Template({ children }: { children: React.ReactNode }) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}
