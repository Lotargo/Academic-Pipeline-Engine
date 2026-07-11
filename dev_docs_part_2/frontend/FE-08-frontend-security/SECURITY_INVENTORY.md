# FE-08 frontend security inventory

## Content sinks

| Sink | Finding | Policy |
|---|---|---|
| `document-preview.tsx` Markdown | Renders React text nodes; no raw HTML parser or `dangerouslySetInnerHTML` | Keep Markdown as text/React nodes. Do not introduce HTML rendering without an approved sanitizer and regression test. |
| `academic-logo-icon.tsx` | Inline CSS is a static component constant | Permitted static-only sink. No props or user data may enter the string. |
| `components/ui/chart.tsx` | Inline CSS derives from chart configuration | Chart keys and CSS color values are allow-listed before insertion. |

No `eval`, `new Function`, DOM HTML assignment, `postMessage`, or untrusted HTML renderer was found in application source during FE-08 inventory.

## Session and browser storage

- Access and refresh tokens are HttpOnly, `SameSite=Lax` cookies set only by `auth-server.ts`; they are not stored in Web Storage.
- `sessionStorage` stores only the selected job ID. `localStorage` stores presentation preferences (nickname, avatar, viewed papers, sidebar width), never credentials or session tokens.
- State-changing `/api` requests are origin-checked in `proxy.ts`; `SameSite=Lax` remains a second browser-level defense.

## External content

- Payment, QR and Telegram URLs are accepted only as `https:` URLs and use `noopener noreferrer`.
- CSP permits an external image origin only when it is the configured SБП QR origin; no wildcard host source is used.
