/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  devIndicators: false,
  async rewrites() {
    const backendUrl = process.env.BACKEND_API_URL || 'http://127.0.0.1:8000';
    return [
      {
        source: '/api/:path((?!jobs(?:/|$)).*)',
        destination: `${backendUrl}/api/:path*`,
      },
    ]
  },
}

export default nextConfig
