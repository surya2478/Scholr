"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, api, type Me } from "@/lib/api";
import { devSignIn } from "@/lib/devAuth";
import { clearToken, getToken } from "@/lib/session";

// Where the app opens. With AUTH_MODE=local (docs/STUDENT-APP.md D7) that is the sign-in page; in development
// mode the seeded household account is opened straight away and the Student/Parent switch changes account.
export default function Entry() {
  const router = useRouter();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const go = (me: Me) => {
      if (cancelled) return;
      const home =
        me.user.role === "student" ? "/student" : me.user.role === "admin" ? "/admin/registrations" : "/parent";
      router.replace(home);
    };
    (async () => {
      try {
        go(getToken() ? await api<Me>("/me") : await devSignIn("student"));
      } catch {
        clearToken();
        try {
          go(await devSignIn("student"));
        } catch (err) {
          // 404: the API is not in development mode, so it expects an email and password.
          if (err instanceof ApiError && err.status === 404) router.replace("/sign-in");
          else if (!cancelled) setFailed(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  return (
    <main className="flex min-h-screen items-center justify-center px-4 bg-ground">
      <div className="card flex w-full max-w-md flex-col items-center gap-4 p-8 text-center rounded-3xl border border-[#FFE8CD] bg-white shadow-lg">
        <div className="relative">
          <div className="flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-tr from-[#FF7A00] to-[#FFA940] text-white shadow-md text-3xl font-fun font-bold animate-pulse">
            🦉
          </div>
          <span className="absolute -bottom-1 -right-1 flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500 text-white text-xs font-bold ring-2 ring-white">
            ⚡
          </span>
        </div>

        <div>
          <h1 className="font-fun text-3xl font-extrabold tracking-tight text-ink">
            Scholr
          </h1>
          <p className="mt-1 text-xs font-medium text-muted">
            Cambridge IGCSE & IIT Foundation Study Space
          </p>
        </div>

        {failed ? (
          <div className="flex flex-col gap-2 rounded-2xl border border-rose-200 bg-rose-50/70 p-4 text-xs text-rose-900">
            <span className="font-bold text-sm">Development API Required</span>
            <p className="text-rose-800">
              The API needs to be running in development mode on this machine to create your session.
            </p>
            <p className="text-[11px] text-muted mt-1">
              Start the backend service and reload this page to enter.
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 pt-2">
            <div className="h-2 w-28 overflow-hidden rounded-full bg-sand">
              <div className="h-full w-full bg-gradient-to-r from-brand to-brand-strong animate-[pulse_1.2s_ease-in-out_infinite]" />
            </div>
            <p className="text-xs font-semibold text-ink-2">Opening your learning space…</p>
          </div>
        )}
      </div>
    </main>
  );
}
