# Provider settings API contract

Контракт используют FE-05 и будущая HTTP-адаптация backend. Каждый endpoint
требует Bearer access token. Backend выбирает workspace по активному membership:
клиент не передаёт `workspace_id`.

## Snapshot and selection

- `GET /api/provider-settings` возвращает один `ProviderSettingsSnapshot`.
- `PUT /api/provider-settings` принимает
  `{ "provider_id": string, "model_id": string, "credential_policy": "platform_first" | "user_only" }`
  и возвращает обновлённый `selection`.
- `user_only` допустим только при активном credential текущего workspace для
  выбранного provider. `platform_first` разрешает безопасный BYOK fallback.

```ts
type Provider = {
  id: string; display_name: string; models: Array<{
    id: string; capabilities: string[]
  }>
  availability: "available" | "degraded" | "exhausted" | "unavailable"
  supports_byok: boolean
}
type ProviderSelection = {
  provider_id: string; model_id: string
  credential_policy: "platform_first" | "user_only"
}
type ProviderSettingsSnapshot = {
  providers: Provider[]; credentials: CredentialMetadata[]
  selection: ProviderSelection | null
}
```

`availability` описывает только текущую возможность использовать platform
resource. Точный остаток, баланс или недокументированная квота в response не
передаются: неизвестная ёмкость отображается как best-effort availability.

## Credentials

- `POST /api/credentials` принимает `{ "provider_id", "label", "secret" }`
  и возвращает `CredentialMetadata` с `201`.
- `PATCH /api/credentials/{credential_id}` принимает `{ "secret" }` и
  возвращает обновлённый `CredentialMetadata`.
- `DELETE /api/credentials/{credential_id}` возвращает `204`. UI всегда
  запрашивает явное подтверждение до вызова этого endpoint.

```ts
type CredentialMetadata = {
  id: string; provider_id: string; label: string
  status: "active" | "disabled" | "deleted"
  masked_value: "••••••••"
  validation: "valid" | "invalid" | "unknown"
  created_at: string; updated_at: string
}
```

Response никогда не содержит исходный `secret`, ciphertext, nonce, wrapped key,
storage key или provider credential ID. Все list/create/replace/delete операции
повторно проверяют membership и не раскрывают наличие credential другого tenant.
