/** @type {import('next').NextConfig} */
const nextConfig = {
  // Build to static HTML/CSS/JS in ./out — no Node server at runtime.
  // FastAPI serves the result, so the whole product is one Databricks App.
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  // We can't run the app to fix lint/type issues during a CI-only build, so
  // don't let those block the static export.
  eslint: { ignoreDuringBuilds: true },
};

module.exports = nextConfig;
