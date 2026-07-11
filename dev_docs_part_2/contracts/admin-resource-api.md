# Admin resource API contract

Контракт используют FE-06, HTTP-адаптация BE-05/BE-08/BE-09 и будущая
observability-композиция. Все endpoints требуют Bearer access token с ролью
`admin`: отсутствие токена возвращает `401`, любая другая роль — `403`.

## Resource snapshot

- `GET /api/admin/resources` возвращает единый `AdminResourceSnapshot`.
- Snapshot read-only. Изменение platform credentials, routing policy или
  fair-use лимитов не добавляется без отдельного versioned extension этого
  контракта, explicit confirmation в UI и audit event на backend.

```ts
type AdminResourceProvider = {
  id: string; display_name: string
  models: Array<{ id: string; capabilities: string[] }>
  health: "healthy" | "degraded" | "open" | "unknown"
  availability: "available" | "degraded" | "exhausted" | "unavailable"
  supports_byok: boolean
  platform_credential: CredentialMetadata | null
  budget: { kind: "known"; limit: string; used: string } | { kind: "unknown" }
}
type FairUsePolicy = {
  max_active_per_user: number; max_queued_per_user: number
}
type AdminResourceSnapshot = {
  providers: AdminResourceProvider[]
  fair_use: FairUsePolicy
  generated_at: string
}
```

`limit` и `used` — decimal strings configured by the service, not a claimed
upstream account balance. Для `kind: "unknown"` числовые поля отсутствуют.
Клиент не вычисляет и не показывает «точный остаток» неизвестной квоты.

## Credential metadata

```ts
type CredentialMetadata = {
  id: string; label: string
  status: "active" | "disabled" | "deleted"
  validation: "valid" | "invalid" | "unknown"
  created_at: string; updated_at: string
}
```

Response никогда не содержит plaintext `secret`, ciphertext, nonce, wrapped
key, storage key, provider-side credential identifier или metadata пользовательских
credentials. Администратор видит только metadata platform credential; ключи
конкретных пользователей не включаются в snapshot.

## Errors and compatibility

- `401` — missing, expired или invalid access token;
- `403` — authenticated caller is not an administrator;
- `503` — resource registry или health source temporarily unavailable. UI
  показывает retry state, не подменяя данные выдуманными значениями.

Новые поля добавляются только как optional. Новые action endpoints сначала
фиксируются в новой версии этого документа и требуют backend authorization,
audit event и явного подтверждения в UI.
