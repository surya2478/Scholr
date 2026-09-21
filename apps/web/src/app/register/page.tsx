"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { register, streamChoices, type StreamChoice } from "@/lib/auth";
import { Button, ErrorNote } from "@/components/ui";

// Registration (docs/STUDENT-APP.md D7): the account is created `pending` and the admin decides what it may see.
// The streams offered come from the API, so this page names none of them itself (AC-U1).
export default function Register() {
  const [streams, setStreams] = useState<StreamChoice[]>([]);
  const [chosen, setChosen] = useState<string[]>([]);
  const [form, setForm] = useState({ display_name: "", email: "", password: "", note: "" });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState("");
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    streamChoices().then(setStreams).catch(setError);
  }, []);

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [key]: e.target.value });

  const toggle = (key: string) =>
    setChosen((current) => (current.includes(key) ? current.filter((k) => k !== key) : [...current, key]));

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const out = await register({ ...form, requested_streams: chosen });
      setDone(out.message);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-ground px-4 py-10">
      <div className="w-full max-w-md rounded-3xl border-2 border-amber-200/80 bg-white p-8 shadow-lg">
        <h1 className="font-fun text-2xl font-extrabold text-ink">Create an account</h1>
        <p className="mt-1 text-xs text-muted">
          Registering does not open the app. An admin reviews every new account and chooses what it can see.
        </p>

        {done ? (
          <div className="mt-6 flex flex-col gap-3">
            <div className="rounded-2xl border-2 border-emerald-200 bg-emerald-50/80 p-4 text-sm text-emerald-900">
              {done}
            </div>
            <Link href="/sign-in" className="text-center text-xs font-bold text-orange-600 hover:underline">
              Back to sign in
            </Link>
          </div>
        ) : (
          <form className="mt-6 flex flex-col gap-3" onSubmit={submit}>
            <label className="flex flex-col gap-1 text-sm font-semibold text-slate-700">
              Your name
              <input
                required
                value={form.display_name}
                onChange={set("display_name")}
                className="h-11 rounded-2xl border-2 border-amber-200 px-3 text-sm font-normal outline-none focus:border-orange-400"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm font-semibold text-slate-700">
              Email
              <input
                type="email"
                required
                autoComplete="email"
                value={form.email}
                onChange={set("email")}
                className="h-11 rounded-2xl border-2 border-amber-200 px-3 text-sm font-normal outline-none focus:border-orange-400"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm font-semibold text-slate-700">
              Password
              <input
                type="password"
                required
                minLength={10}
                autoComplete="new-password"
                value={form.password}
                onChange={set("password")}
                className="h-11 rounded-2xl border-2 border-amber-200 px-3 text-sm font-normal outline-none focus:border-orange-400"
              />
              <span className="text-[11px] font-normal text-muted">At least 10 characters.</span>
            </label>

            <fieldset className="flex flex-col gap-2 rounded-2xl border-2 border-amber-200 p-3">
              <legend className="px-1 text-sm font-semibold text-slate-700">What would you like to study?</legend>
              {streams.map((stream) => (
                <label key={stream.key} className="flex items-start gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={chosen.includes(stream.key)}
                    disabled={stream.status === "later"}
                    onChange={() => toggle(stream.key)}
                    className="mt-1"
                  />
                  <span>
                    {stream.name}
                    {stream.status === "later" && <span className="ml-1 text-xs text-muted">(not open yet)</span>}
                  </span>
                </label>
              ))}
            </fieldset>

            <label className="flex flex-col gap-1 text-sm font-semibold text-slate-700">
              Anything the admin should know (optional)
              <textarea
                rows={2}
                value={form.note}
                onChange={set("note")}
                className="rounded-2xl border-2 border-amber-200 p-3 text-sm font-normal outline-none focus:border-orange-400"
              />
            </label>

            {error ? <ErrorNote error={error} /> : null}

            <Button type="submit" disabled={busy} className="mt-1 w-full">
              {busy ? "Sending…" : "Request access"}
            </Button>
            <Link href="/sign-in" className="text-center text-xs font-bold text-orange-600 hover:underline">
              I already have an account
            </Link>
          </form>
        )}
      </div>
    </main>
  );
}
