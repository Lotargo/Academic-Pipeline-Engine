# Provider-only auth contract

Используется `BE-13` и `FE-12`. Service-профиль принимает только bearer token
выбранного external identity adapter; legacy APE password JWT допускается лишь
при явном `APE_IDENTITY_ADAPTER=legacy` и не смешивается с этим контрактом.

## Identity boundary

После криптографической проверки adapter передаёт backend только:

```text
issuer: string                 # Supabase Auth issuer
provider: "google" | "yandex" # production external providers
provider_subject: UUID string  # immutable Supabase auth.users.id
email: normalized string       # display/provisioning metadata, не lookup key
```

APE создаёт link по `(issuer, provider_subject)` и хранит также уникальную
пару `(provider, provider_subject)`. Email никогда не присоединяет новый
external identity к существующему legacy user. Повторный вход с тем же subject
возвращает того же user и personal workspace; app RBAC и workspace checks
применяются после этого resolution.

Supabase adapter принимает только JWT с проверенной asymmetric подписью из
JWKS, допустимыми `iss`, `aud=authenticated`, `exp`, UUID `sub` и
`role=authenticated`. Unknown `kid` делает не более одного принудительного
refresh JWKS и затем fail-closed.

## Service backend

- `GET /api/auth/context` — требует provider bearer token и возвращает
  `{user_id, email, role, workspaces}`. Первый успешный запрос провижинит
  app user/workspace/link транзакционно.
- Service router не монтирует `POST /api/auth/register`, `/login`, `/refresh`
  и `/logout`; их отсутствие является profile boundary, а не ошибкой UI.
- `401` означает invalid/expired/wrong issuer/audience external identity;
  `403` — blocked app user; `409` — безопасный provisioning conflict, например
  существующий legacy account с тем же email без identity link.

## Frontend BFF

Browser обращается только к Next routes:

- `GET /api/auth/providers/google/start` и `/yandex/start`;
- `GET /api/auth/callback`;
- `GET /api/auth/session`;
- `POST /api/auth/logout`.

В `service-dev` дополнительно доступен `POST /api/auth/email/start`. Он
выдаёт только local `mock:email:<normalized-email>` identity и не вызывает
почтовый сервис: письмо и код намеренно отсутствуют. Backend детерминированно
провижинит/находит personal workspace для этого email. В `supabase`-режиме
маршрут отвечает `404`; это не password login и не production email auth.

`ape_identity_access`, refresh token и PKCE state/verifier — HTTP-only,
`SameSite=Lax` cookies; они не записываются в `localStorage` или
`sessionStorage`. `/auth/callback` показывает `complete`, `cancelled`,
`denied` либо `provider_error`, но не является proof of access: protected
routes ждут server-side `/api/auth/context`.

`mock` — явный local/service-dev adapter с `mock:<provider>` и
`mock:email:<email>` cookie token, визуальной маркировкой и без обращения к
OAuth или почтовому сервису. `supabase` использует PKCE и
server-side token exchange. Для Яндекса deployment задаёт поддерживаемый
Supabase custom OAuth/OIDC provider alias в `APE_SUPABASE_YANDEX_PROVIDER_ID`.
`APE_PUBLIC_APP_ORIGIN` — server-only canonical origin callback; в
`service-dev` это `http://localhost:3000`, а в deployment — public HTTPS URL.

## Production gate

Google/Яндекс application credentials, Supabase `SITE_URL`, точные redirect
allow-list и canonical HTTPS URL отсутствуют в репозитории. Реальный provider
OAuth считается готовым только после E2E на постоянном deployment URL;
локальный mock и contract tests этот gate не закрывают.
