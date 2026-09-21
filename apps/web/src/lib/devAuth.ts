"use client";

import { api, type Me } from "./api";
import { setToken } from "./session";

// Sign-in is not built yet (CONTEXT U6: hosting and identity provider undecided), so the app opens straight into
// the household. The API hands out a token for a seeded account only when it runs with AUTH_MODE=dev; anywhere
// else the route reports 404 and the app says sign-in is not set up.
export type DevRole = "student" | "guardian";

export async function devSignIn(role: DevRole): Promise<Me> {
  const session = await api<{ token: string; role: string; display_name: string }>("/dev/session", {
    method: "POST",
    json: { role },
  });
  setToken(session.token);
  return api<Me>("/me");
}
