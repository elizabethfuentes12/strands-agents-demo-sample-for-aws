// Cognito USER_PASSWORD_AUTH via the public InitiateAuth API (no SDK needed).
import { config } from '../config'

const STORAGE_KEY = 'strands-demos-auth'

interface StoredAuth {
  accessToken: string
  expiresAt: number
}

export async function login(username: string, password: string): Promise<string> {
  const res = await fetch(`https://cognito-idp.${config.region}.amazonaws.com/`, {
    method: 'POST',
    headers: {
      'content-type': 'application/x-amz-json-1.1',
      'x-amz-target': 'AWSCognitoIdentityProviderService.InitiateAuth',
    },
    body: JSON.stringify({
      AuthFlow: 'USER_PASSWORD_AUTH',
      ClientId: config.userPoolClientId,
      AuthParameters: { USERNAME: username, PASSWORD: password },
    }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.message ?? `Login failed (${res.status})`)
  }
  const data = await res.json()
  const result = data.AuthenticationResult
  if (!result?.AccessToken) throw new Error('Login incomplete (password change required?)')
  const stored: StoredAuth = {
    accessToken: result.AccessToken,
    expiresAt: Date.now() + (result.ExpiresIn ?? 3600) * 1000,
  }
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(stored))
  return stored.accessToken
}

export function getToken(): string | null {
  const raw = sessionStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  try {
    const stored: StoredAuth = JSON.parse(raw)
    // 5-minute safety margin before expiry.
    if (stored.expiresAt - 300_000 < Date.now()) return null
    return stored.accessToken
  } catch {
    return null
  }
}

export function logout(): void {
  sessionStorage.removeItem(STORAGE_KEY)
}
