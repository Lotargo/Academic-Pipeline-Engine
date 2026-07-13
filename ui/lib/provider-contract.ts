export type Availability = "available" | "degraded" | "exhausted" | "unavailable"
export type CredentialPolicy = "platform_first" | "user_only"
export type CredentialStatus = "active" | "disabled" | "deleted"
export type ValidationState = "valid" | "invalid" | "unknown"

export type ProviderModel = { id: string; capabilities: string[] }
export type Provider = { id: string; display_name: string; models: ProviderModel[]; availability: Availability; supports_byok: boolean }
export type CredentialMetadata = {
  id: string; provider_id: string; label: string; status: CredentialStatus
  masked_value: "••••••••"; validation: ValidationState; created_at: string; updated_at: string
}
export type ProviderSelection = { provider_id: string; model_id: string; credential_policy: CredentialPolicy }
export type ProviderSettingsSnapshot = { providers: Provider[]; credentials: CredentialMetadata[]; selection: ProviderSelection | null }

const availability = new Set<Availability>(["available", "degraded", "exhausted", "unavailable"])
const credentialPolicy = new Set<CredentialPolicy>(["platform_first", "user_only"])
const credentialStatus = new Set<CredentialStatus>(["active", "disabled", "deleted"])
const validationState = new Set<ValidationState>(["valid", "invalid", "unknown"])

const isRecord = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === "object" && !Array.isArray(value)
const string = (value: unknown, fallback = ""): string => typeof value === "string" ? value : fallback

function model(value: unknown): ProviderModel | null {
  if (!isRecord(value) || !string(value.id)) return null
  return { id: string(value.id), capabilities: Array.isArray(value.capabilities) ? value.capabilities.filter((capability): capability is string => typeof capability === "string") : [] }
}

function provider(value: unknown): Provider | null {
  if (!isRecord(value) || !string(value.id) || !availability.has(value.availability as Availability)) return null
  return {
    id: string(value.id), display_name: string(value.display_name, string(value.id)),
    models: Array.isArray(value.models) ? value.models.map(model).filter((item): item is ProviderModel => item !== null) : [],
    availability: value.availability as Availability, supports_byok: Boolean(value.supports_byok),
  }
}

function credential(value: unknown): CredentialMetadata | null {
  if (!isRecord(value) || !string(value.id) || !string(value.provider_id) || !credentialStatus.has(value.status as CredentialStatus)) return null
  return {
    id: string(value.id), provider_id: string(value.provider_id), label: string(value.label, "API key"),
    status: value.status as CredentialStatus,
    // The browser deliberately renders a fixed mask; it never reads an upstream secret-like field.
    masked_value: "••••••••",
    validation: validationState.has(value.validation as ValidationState) ? value.validation as ValidationState : "unknown",
    created_at: string(value.created_at), updated_at: string(value.updated_at),
  }
}

function selection(value: unknown): ProviderSelection | null {
  if (!isRecord(value) || !string(value.provider_id) || !string(value.model_id) || !credentialPolicy.has(value.credential_policy as CredentialPolicy)) return null
  return { provider_id: string(value.provider_id), model_id: string(value.model_id), credential_policy: value.credential_policy as CredentialPolicy }
}

export function providerSettingsSnapshot(value: unknown): ProviderSettingsSnapshot {
  const data = isRecord(value) ? value : {}
  return {
    providers: Array.isArray(data.providers) ? data.providers.map(provider).filter((item): item is Provider => item !== null) : [],
    credentials: Array.isArray(data.credentials) ? data.credentials.map(credential).filter((item): item is CredentialMetadata => item !== null) : [],
    selection: selection(data.selection),
  }
}

export function credentialMetadata(value: unknown): CredentialMetadata | null { return credential(value) }
