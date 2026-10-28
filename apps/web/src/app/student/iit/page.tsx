"use client";

import Link from "next/link";
import { ReinforcementList, StandingCards } from "@/components/Reinforcement";
import { Card, Chip, Empty, ErrorNote } from "@/components/ui";
import type { ExternalSummary, Stream } from "@/lib/api";
import { minutes, shortDate } from "@/lib/format";
import { useApi } from "@/lib/useApi";

// The student's view of her own IIT classes. She (or a parent) logs a class from its lesson page; Scholr's job here
// is to say what it means for her IGCSE work — never to set her more of the same (PHASE-3 §1).
export default function StudentIit() {
  const summary = useApi<ExternalSummary>("/external-training/summary");
  const streams = useApi<Stream[]>("/learn/streams");
  const iitSubjects = (streams.data ?? []).flatMap((s) => s.subjects).filter((s) => s.stage === "external");
  const logs = summary.data?.recent ?? [];

  return (
    <div className="space-y-6">
      {/* IIT Foundation bridge header */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-[#0B1528] via-[#1E1B4B] to-[#312E81] p-6 md:p-8 text-white shadow-xl">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-5">
          <div className="space-y-2 text-center sm:text-left">
            <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/10 text-emerald-300 font-mono text-xs font-bold border border-white/15">
                <span>🏛️</span> IIT FOUNDATION BRIDGE
              </span>
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-blue-500/20 text-blue-200 font-mono text-[11px] font-bold border border-blue-400/30">
                <span>⚡</span> CAMBRIDGE CIE ↔ JEE FOUNDATION
              </span>
            </div>
            <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
              IIT Foundation Standing &amp; IGCSE Groundwork
            </h1>
            <p className="text-xs md:text-sm text-slate-300 font-medium max-w-2xl leading-relaxed">
              Maps your external IIT Foundation classes and test scores directly to the Cambridge IGCSE Extended prerequisites underneath them.
            </p>
          </div>
          <div className="h-16 w-16 rounded-2xl bg-white/10 border border-white/15 flex items-center justify-center font-mono text-xl font-extrabold text-emerald-300 flex-none">
            IIT
          </div>
        </div>
      </div>

      {summary.error ? <ErrorNote error={summary.error} /> : null}

      {/* Step 5: every IIT course is navigable lesson by lesson (docs/STUDENT-APP.md). */}
      {iitSubjects.length > 0 && (
        <Card title="📚 Your IIT lessons, chapter by chapter" subtitle="Open a lesson to log a class, see the IGCSE ground under it, and warm up" tone="purple">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {iitSubjects.map((subject) => (
              <Link
                key={subject.id}
                href={`/student/learn/subject/${subject.id}`}
                className="flex items-center justify-between rounded-2xl border border-purple-200 bg-white px-4 py-3 text-sm font-fun font-bold text-slate-900 hover:border-purple-400"
              >
                <span>{subject.name}</span>
                <span className="text-xs font-semibold text-slate-500">{subject.objectives} lessons →</span>
              </Link>
            ))}
          </div>
        </Card>
      )}

      <Card
        title="📊 How It's Going"
        subtitle="Progress and syllabus coverage calculated from your external coaching logs"
        tone="purple"
      >
        <StandingCards subjects={summary.data?.subjects ?? []} />
      </Card>

      <ReinforcementList
        targets={summary.data?.reinforcement ?? []}
        subtitle="Cambridge IGCSE topics that build the ground under difficult coaching sessions. Practise these before your next class!"
        emptyText="Nothing here right now — suggestions appear when a challenging class is recorded."
      />

      <Card
        title="🕒 Your Recent External Classes"
        subtitle="Recorded study sessions, homework, and test milestones"
        tone="amber"
      >
        {logs.length === 0 && <Empty>No coaching sessions recorded yet.</Empty>}
        <ul className="flex flex-col gap-2.5">
          {logs.map((log) => (
            <li
              key={log.id}
              className="flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200/90 bg-white p-3.5 shadow-2xs transition hover:border-purple-300"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-50 text-lg">
                🚀
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <b className="font-fun font-bold text-slate-900">{log.title}</b>
                  <span className="rounded-full bg-purple-100 px-2 py-0.5 text-[11px] font-bold text-purple-800 capitalize">
                    {log.kind}
                  </span>
                </div>
                <div className="text-xs text-slate-500 font-medium mt-0.5">
                  {log.subject_name} · 📅 {shortDate(log.occurred_on)}
                  {log.duration_min ? ` · ⏱️ ${minutes(log.duration_min)}` : ""}
                </div>
              </div>
              {log.lessons.length > 0 && (
                <span className="text-xs text-purple-700 bg-purple-50 px-2.5 py-1 rounded-xl font-medium border border-purple-100 truncate max-w-xs">
                  {log.lessons.map((l) => l.title).join(", ")}
                </span>
              )}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
