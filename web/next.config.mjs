/** @type {import('next').NextConfig} */
const nextConfig = {
  // Self-contained server bundle for the Docker image (see web/Dockerfile).
  output: "standalone",
  reactStrictMode: true,
};

export default nextConfig;
