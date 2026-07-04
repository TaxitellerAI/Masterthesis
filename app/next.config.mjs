/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // pdf-lib is a pure-JS dependency; nothing special needed, but we keep the
  // server external list explicit so the PDF route bundles cleanly.
  serverExternalPackages: ["pdf-lib"],
};

export default nextConfig;
