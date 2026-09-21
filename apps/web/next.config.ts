import type { NextConfig } from "next";

// The browser talks only to this origin; /api/* is proxied to the FastAPI server, so the API needs no CORS.
const apiOrigin = process.env.SCHOLR_API_ORIGIN ?? "http://127.0.0.1:8000";

const config: NextConfig = {
  reactStrictMode: true,
  // The container image runs `node server.js` with only the files the app needs (apps/web/Dockerfile).
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/:path*` }];
  },
};

export default config;
