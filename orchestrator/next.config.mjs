/** @type {import("next").NextConfig} */
const nextConfig = {
  typedRoutes: true,
  output: "standalone",
  experimental: {
    serverActions: {
      bodySizeLimit: "2mb"
    }
  }
}

export default nextConfig
