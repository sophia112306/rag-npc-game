import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The local demo may be opened through either loopback hostname. Without
  // this, Next.js serves the HTML at 127.0.0.1 but blocks development assets,
  // leaving React controls visible yet non-interactive.
  allowedDevOrigins: ["127.0.0.1"],
  experimental: {
    agentUpgrade: "security",
  },
  turbopack: {
    root: process.cwd(),
  },
};

export default nextConfig;
