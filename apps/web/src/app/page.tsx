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
    <main className="flex min-h-screen items-center justify-center px-4 bg-[#0B1528] text-white">
      <div className="flex w-full max-w-md flex-col items-center gap-5 p-8 text-center rounded-3xl border border-slate-800 bg-[#111C35] shadow-2xl">
        <div className="relative">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-tr from-blue-600 via-indigo-500 to-emerald-400 text-white shadow-lg font-mono text-2xl font-extrabold animate-pulse">
            S
          </div>
        </div>

        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-white">
            SCHOLR <span className="font-mono text-sm text-emerald-400">PRO</span>
          </h1>
          <p className="mt-1 text-xs font-medium text-slate-400">
            Cambridge IGCSE Extended &amp; IIT Foundation Academic Studio
          </p>
        </div>

        {failed ? (
          <div className="flex flex-col gap-2 rounded-2xl border border-rose-500/30 bg-rose-950/50 p-4 text-xs text-rose-200">
            <span className="font-bold text-sm">Development API Required</span>
            <p>
              The API service needs to be running on port 8000 to initialise your session.
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 pt-2">
            <div className="h-1.5 w-32 overflow-hidden rounded-full bg-slate-800">
              <div className="h-full w-full bg-gradient-to-r from-blue-500 to-emerald-400 animate-[pulse_1.2s_ease-in-out_infinite]" />
            </div>
            <p className="text-xs font-semibold text-slate-300">Initialising academic workspace…</p>
          </div>
        )}
      </div>
    </main>
  );
}
