"use client";

import { Card, Chip, Empty, ErrorNote } from "@/components/ui";
import type { Memory } from "@/lib/api";
import { shortDate } from "@/lib/format";
import { useApi } from "@/lib/useApi";
import { useLinkedStudent } from "@/lib/useStudent";

const TONE: Record<string, "good" | "warn" | "alert" | "brand" | "neutral"> = {
  strength: "good",
  difficulty: "warn",
  misconception: "alert",
  preference: "brand",
  note: "neutral",
};

export default function Notes() {
  const { id, query, has } = useLinkedStudent();
  const notes = useApi<Memory[]>(id && has("memory") ? `/memory?${query}` : null);

  const kindMeta: Record<string, { icon: string; label: string; tone: "good" | "warn" | "alert" | "brand" | "neutral"; bg: string }> = {
    strength: { icon: "💪", label: "Strength", tone: "good", bg: "bg-emerald-50/70 border-emerald-200/60" },
    difficulty: { icon: "🧗", label: "Challenge Area", tone: "warn", bg: "bg-amber-50/70 border-amber-200/60" },
    misconception: { icon: "🔍", label: "Misconception", tone: "alert", bg: "bg-rose-50/70 border-rose-200/60" },
    preference: { icon: "🎨", label: "Preference", tone: "brand", bg: "bg-purple-50/70 border-purple-200/60" },
    note: { icon: "📝", label: "Observation", tone: "neutral", bg: "bg-stone-50/70 border-stone-200/60" },
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Friendly banner */}
      <section className="relative overflow-hidden rounded-3xl border border-[#FFE8CD] bg-gradient-to-r from-[#FFF7ED] via-[#FFFDF9] to-[#F5F3FF] p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-white/90 px-3 py-1 text-xs font-bold text-amber-800 shadow-xs">
              <span>🧠</span> Pedagogical Memory
            </div>
            <h1 className="mt-2 text-2xl font-fun font-extrabold tracking-tight text-ink">
              Learning Notes & Study Insights
            </h1>
            <p className="mt-1 max-w-xl text-sm text-ink-2">
              Scholr continuously distils what helps your child learn best: core strengths, recurring misconceptions, and study preferences. Each note is grounded in actual practice evidence.
            </p>
          </div>
          <div className="flex items-center gap-3 rounded-2xl border border-amber-200/60 bg-white/90 p-4 shadow-xs">
            <div className="text-3xl">🔍</div>
            <div>
              <div className="text-xs font-bold text-muted uppercase tracking-wider">Evidence Grounded</div>
              <div className="font-fun text-sm font-bold text-ink">Zero Hallucination</div>
              <div className="text-[11px] text-muted">Directly tied to step logs</div>
            </div>
          </div>
        </div>
      </section>

      <Card
        title="Distilled Insights"
        subtitle="Opening this page is logged in the family transparency trail to preserve trust."
      >
        {!has("memory") && <Empty>Your parent account does not have permission to view learning notes.</Empty>}
        {notes.error ? <ErrorNote error={notes.error} /> : null}
        {notes.data?.length === 0 && (
          <Empty>No learning memory notes yet. They are synthesized after student study sessions are completed and summarized.</Empty>
        )}
        <ul className="flex flex-col gap-3">
          {notes.data?.map((n) => {
            const meta = kindMeta[n.kind] ?? { icon: "📌", label: n.kind, tone: "neutral", bg: "bg-white border-line-soft" };
            return (
              <li
                key={n.id}
                className={`flex flex-col gap-2 rounded-2xl border p-4 shadow-xs transition hover:shadow-sm ${meta.bg}`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-base">{meta.icon}</span>
                    <Chip tone={meta.tone}>{meta.label}</Chip>
                  </div>
                  <span className="rounded-full bg-white/80 px-2.5 py-0.5 text-[11px] font-semibold text-muted shadow-xs">
                    📅 {shortDate(n.updated_at)}
                  </span>
                </div>
                <p className="font-medium text-sm text-ink leading-relaxed pl-1">
                  {n.statement}
                </p>
                <div className="flex items-center justify-between pt-1 text-[11px] text-muted pl-1 border-t border-line-soft/60">
                  <span className="font-semibold text-ink-2">
                    🎯 Supported by {n.evidence_count} piece{n.evidence_count === 1 ? "" : "s"} of session evidence
                  </span>
                  <span className="text-[10px] text-muted">Audited insight</span>
                </div>
              </li>
            );
          })}
        </ul>
      </Card>
    </div>
  );
}
