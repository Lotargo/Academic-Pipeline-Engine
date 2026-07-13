/** @type {import('next').NextConfig} */
function configuredHttpsOrigin(template) {
  try {
    const url = new URL((template || '').replaceAll('{amount}', '500'))
    return url.protocol === 'https:' ? url.origin : null
  } catch {
    return null
  }
}

const supportQrOrigin = configuredHttpsOrigin(process.env.NEXT_PUBLIC_SUPPORT_SBP_QR_URL_TEMPLATE)
const contentSecurityPolicy = [
  "default-src 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  `img-src 'self' data: blob:${supportQrOrigin ? ` ${supportQrOrigin}` : ''}`,
  "font-src 'self'",
  "connect-src 'self'",
  "worker-src 'self' blob:",
  "frame-src 'none'",
].join('; ')

const nextConfig = {
  output: 'standalone',
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  devIndicators: false,
  async headers() {
    const securityHeaders = [
      { key: 'Content-Security-Policy', value: contentSecurityPolicy },
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'X-Frame-Options', value: 'DENY' },
      { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
      { key: 'Permissions-Policy', value: 'camera=(), geolocation=(), microphone=(), payment=(), usb=()' },
      { key: 'Cross-Origin-Opener-Policy', value: 'same-origin' },
      { key: 'Cross-Origin-Resource-Policy', value: 'same-origin' },
      { key: 'X-DNS-Prefetch-Control', value: 'off' },
    ]
    if (process.env.NODE_ENV === 'production') securityHeaders.push({ key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains; preload' })
    return [{ source: '/:path*', headers: securityHeaders }]
  },
  async rewrites() {
    const backendUrl = process.env.BACKEND_API_URL || 'http://127.0.0.1:8000';
    return [
      {
        // Auth routes are a first-party BFF boundary: provider callbacks and
        // HTTP-only session cookies must never be proxied straight to FastAPI.
        source: '/api/:path((?!(?:jobs|auth|provider-settings|credentials|settings)(?:/|$)).*)',
        destination: `${backendUrl}/api/:path*`,
      },
    ]
  },
}

export default nextConfig
