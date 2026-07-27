import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a self-contained production server under .next/standalone
  // (a minimal server.js + pruned node_modules). This is what the
  // Docker runtime image runs — it keeps the image small and needs no
  // dev dependencies or full node_modules at runtime. No effect on
  // `next dev`; purely a production build-output option.
  output: "standalone",
};

export default nextConfig;
