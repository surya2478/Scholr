"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError } from "@/lib/api";
import { signIn } from "@/lib/auth";
import { Button, ErrorNote } from "@/components/ui";

// Email and password sign-in (docs/STUDENT-APP.md D7). A new account waits for the admin, so this page says so
// plainly rather than looking like a failure.
export default function SignIn() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const waiting = error instanceof ApiError && error.code === "approval_pending";

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const session = await signIn(email, password);
      router.replace(
        session.role === "student" ? "/student" : session.role === "admin" ? "/admin/registrations" : "/parent",
      );
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-ground px-4 py-10">
      <div className="w-full max-w-md rounded-3xl border-2 border-slate-200/90 bg-white p-8 shadow-lg">
        <div className="flex flex-col items-center gap-2 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-gradient-to-tr from-[#FF7A00] to-[#FFA940] text-3xl text-white shadow-md">
            🦉
          </div>
          <h1 className="font-fun text-2xl font-extrabold text-ink">Sign in to Scholr</h1>
          <p className="text-xs text-muted">Cambridge IGCSE &amp; IIT Foundation Study Space</p>
        </div>

        <form className="mt-6 flex flex-col gap-3" onSubmit={submit}>
          <label className="flex flex-col gap-1 text-sm font-semibold text-slate-700">
            Email
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="h-11 rounded-2xl border-2 border-slate-200 px-3 text-sm font-normal outline-none focus:border-blue-500"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold text-slate-700">
            Password
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="h-11 rounded-2xl border-2 border-slate-200 px-3 text-sm font-normal outline-none focus:border-blue-500"
            />
          </label>

          {waiting ? (
            <div className="rounded-2xl border-2 border-slate-200 bg-amber-50/80 p-4 text-sm text-amber-900">
              Your account is waiting for the admin to approve it. You&apos;ll be able to sign in after that.
            </div>
          ) : error ? (
            <ErrorNote error={error} />
          ) : null}

          <Button type="submit" disabled={busy} className="mt-1 w-full">
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <p className="mt-5 text-center text-xs text-muted">
          New here?{" "}
          <Link href="/register" className="font-bold text-blue-600 hover:underline">
            Create an account
          </Link>
        </p>
      </div>
    </main>
  );
}
