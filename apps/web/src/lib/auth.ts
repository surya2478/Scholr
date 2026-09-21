"use client";

// Email-and-password sign-in (docs/STUDENT-APP.md D7). The API offers these routes only when it runs with
// AUTH_MODE=local; in development mode they report 404 and the app falls back to the seeded household account.

import { ApiError, api } from "./api";
import { setToken } from "./session";

export type StreamChoice = { key: string; name: string; status: string };
export type SignedIn = { token: string; role: string; display_name: string; expires_in_hours: number };

export async function streamChoices(): Promise<StreamChoice[]> {
  return api<StreamChoice[]>("/auth/streams");
}

/** True when the API expects an email and password rather than the development account. */
export async function localSignInEnabled(): Promise<boolean> {
  try {
    await streamChoices();
    return true;
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return false;
    throw err;
  }
}

export async function signIn(email: string, password: string): Promise<SignedIn> {
  const session = await api<SignedIn>("/auth/sign-in", { method: "POST", json: { email, password } });
  setToken(session.token);
  return session;
}

export async function register(body: {
  email: string;
  password: string;
  display_name: string;
  requested_streams: string[];
  note?: string;
}): Promise<{ status: string; message: string }> {
  return api<{ status: string; message: string }>("/auth/register", { method: "POST", json: body });
}

export type PendingAccount = {
  user_id: string;
  email: string;
  display_name: string;
  requested_streams: string[];
  note: string;
  requested_at: string;
};

export async function pendingAccounts(): Promise<PendingAccount[]> {
  return api<PendingAccount[]>("/admin/registrations");
}

export async function approveAccount(
  userId: string,
  body: { role: string; streams: string[]; year_group?: string },
): Promise<{ subjects_enrolled: string[] }> {
  return api<{ subjects_enrolled: string[] }>(`/admin/registrations/${userId}/approve`, {
    method: "POST",
    json: body,
  });
}

export async function rejectAccount(userId: string, reason: string): Promise<void> {
  await api<void>(`/admin/registrations/${userId}/reject`, { method: "POST", json: { reason } });
}
