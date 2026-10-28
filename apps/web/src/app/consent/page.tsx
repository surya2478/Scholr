"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, Card, ErrorNote } from "@/components/ui";
import { api, type Me } from "@/lib/api";
import { SCOPE_LABELS } from "@/lib/format";

type Consent = { id: string; kind: string; policy_version: string; granted_at: string; withdrawn_at: string | null };

// Guardian consent and student assent (identity.consent). Shown once per policy version.
export default function ConsentPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [consents, setConsents] = useState<Consent[]>([]);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api<Me>("/me").then(setMe).catch(() => router.replace("/"));
    api<Consent[]>("/consents").then(setConsents).catch(() => undefined);
  }, [router]);

  const isStudent = me?.user.role === "student";
  const kind = isStudent ? "student_assent" : "guardian_consent";
  const given = consents.find((c) => c.kind === kind && !c.withdrawn_at);
  const scopes = isStudent ? (me?.guardian_visibility[0]?.scopes ?? []) : (me?.linked_students[0]?.scopes ?? []);

  async function agree() {
    setError(null);
    try {
      await api("/consents", { method: "POST", json: {} });
      router.replace(isStudent ? "/student" : "/parent");
    } catch (err) {
      setError(err);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-xl items-center px-4 py-8">
      <div className="card w-full overflow-hidden rounded-3xl border border-[#FFE8CD] bg-white p-6 sm:p-8 shadow-md">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#FFF5EB] text-2xl shadow-xs">
            🦉
          </div>
          <div>
            <div className="inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-2.5 py-0.5 text-[11px] font-bold text-brand-strong">
              <span>🛡️</span> Privacy & Wellbeing
            </div>
            <h1 className="text-xl font-fun font-extrabold text-ink mt-0.5">
              {isStudent ? "Welcome to Scholr! Before We Start" : "Parent & Guardian Consent"}
            </h1>
          </div>
        </div>

        <div className="mt-4 rounded-2xl border border-line-soft bg-gradient-to-b from-[#FFFDF9] to-[#FAF7F0] p-4 text-xs text-ink-2">
          <p className="font-semibold text-ink">
            {isStudent
              ? "Scholr is designed to be your supportive study buddy. Here is how we look after you:"
              : "Scholr provides an evidence-based, Cambridge-verified learning experience with full family transparency:"}
          </p>
          <ul className="mt-3 space-y-2.5">
            <li className="flex items-start gap-2.5">
              <span className="text-base">🔒</span>
              <div>
                <b className="font-bold text-ink">Private to your family:</b> Your answers, workings, and tutor chats are never sold or shared outside your household.
              </div>
            </li>
            <li className="flex items-start gap-2.5">
              <span className="text-base">🤖</span>
              <div>
                <b className="font-bold text-ink">Tutor:</b> The Tutor is an AI assistant, not a human. It quotes your own textbooks and tells you when it uses general knowledge.
              </div>
            </li>
            <li className="flex items-start gap-2.5">
              <span className="text-base">👁️</span>
              <div>
                <b className="font-bold text-ink">{isStudent ? "Parent visibility:" : "What you can see:"}</b> {scopes.map((s) => SCOPE_LABELS[s] ?? s).join(", ") || "—"}. Reciprocal audit logs show every time chats or notes are viewed.
              </div>
            </li>
            <li className="flex items-start gap-2.5">
              <span className="text-base">🛡️</span>
              <div>
                <b className="font-bold text-ink">Child Safety Safeguard:</b> If any interaction indicates distress or danger, Scholr responds with empathetic support and alerts parents immediately.
              </div>
            </li>
            <li className="flex items-start gap-2.5">
              <span className="text-base">⚙️</span>
              <div>
                <b className="font-bold text-ink">Control & Consent:</b> You can withdraw or modify these permissions at any time from your account settings.
              </div>
            </li>
          </ul>
        </div>

        <div className="mt-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-line-soft">
          <span className="text-[11px] text-muted">
            Policy version: <code className="font-mono text-ink-2">privacy_v1</code>
          </span>
          {given ? (
            <div className="flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700">
              <span>✓</span> Agreed on {new Date(given.granted_at).toLocaleDateString("en-GB")}
            </div>
          ) : (
            <Button onClick={agree}>
              {isStudent ? "I understand — Let's Start! 🚀" : "I Give Consent as Guardian ✓"}
            </Button>
          )}
        </div>

        {error ? <div className="mt-3"><ErrorNote error={error} /></div> : null}
      </div>
    </main>
  );
}
