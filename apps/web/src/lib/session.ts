// Development sign-in: the API runs with AUTH_MODE=dev and accepts tokens minted by `app.jobs.dev_token`.
// The token is kept in this browser only. Production sign-in (AUTH_MODE=jwks) replaces this module.

const KEY = "scholr.dev_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    window.localStorage.setItem(KEY, token.trim());
  } catch {
    /* storage blocked: sign-in lasts for this page only */
  }
}

export function clearToken(): void {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
