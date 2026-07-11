import { NextResponse, type NextRequest } from "next/server"

const unsafeMethods = new Set(["DELETE", "PATCH", "POST", "PUT"])

function requestOrigin(request: NextRequest) {
  const forwardedProtocol = request.headers.get("x-forwarded-proto")?.split(",")[0]?.trim()
  const forwardedHost = request.headers.get("x-forwarded-host")?.split(",")[0]?.trim()
  const protocol = forwardedProtocol || request.nextUrl.protocol.replace(/:$/, "")
  const host = forwardedHost || request.headers.get("host") || request.nextUrl.host
  return `${protocol}://${host}`
}

export function proxy(request: NextRequest) {
  if (!unsafeMethods.has(request.method)) return NextResponse.next()

  const origin = request.headers.get("origin")
  if (origin) {
    if (origin === requestOrigin(request)) return NextResponse.next()
    return NextResponse.json({ detail: "Cross-origin request denied" }, { status: 403 })
  }

  // Browsers attach Origin to unsafe fetches. For clients that do not, reject a
  // declared cross-site request while keeping non-browser service clients usable.
  const fetchSite = request.headers.get("sec-fetch-site")
  if (fetchSite && fetchSite !== "same-origin" && fetchSite !== "none") {
    return NextResponse.json({ detail: "Cross-origin request denied" }, { status: 403 })
  }
  return NextResponse.next()
}

export const config = { matcher: "/api/:path*" }
