export type AuthAction = "login" | "register"

export interface Credentials {
  email: string
  password: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: "bearer"
}

export interface AuthErrorPayload {
  code: "invalid_credentials" | "account_blocked" | "email_unavailable" | "validation_error" | "service_unavailable"
  message: string
}

export function publicAuthError(action: AuthAction, status: number): AuthErrorPayload {
  if (status === 403) return { code: "account_blocked", message: "Аккаунт заблокирован. Обратитесь к администратору." }
  if (status === 422) return { code: "validation_error", message: "Проверьте email и пароль. Пароль должен содержать не менее 12 символов." }
  if (action === "register" && status === 409) return { code: "email_unavailable", message: "Не удалось создать аккаунт с этими данными." }
  if (action === "login" && status === 401) return { code: "invalid_credentials", message: "Неверный email или пароль." }
  return { code: "service_unavailable", message: "Сервис авторизации временно недоступен. Попробуйте ещё раз." }
}
