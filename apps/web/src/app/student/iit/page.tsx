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
      {/* Friendly IIT Bridge Header — Warm Purple & Gold Horizon */}
      <div className="relative overflow-hidden rounded-3xl border-2 border-purple-200 bg-gradient-to-br from-[#FAF5FF] via-[#FFF9F2] to-[#F3E8FF] p-6 md:p-8 shadow-sm">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-5">
          <div className="space-y-2 text-center sm:text-left">
            <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-purple-100 text-purple-800 text-xs font-fun font-bold border border-purple-200 shadow-2xs">
                <span>🚀</span> IIT Foundation Bridge
              </span>
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-800 text-[11px] font-fun font-bold border border-amber-200">
                <span>⚡</span> Dual Curriculum
              </span>
            </div>
            <h1 className="text-2xl md:text-3xl font-fun font-bold text-slate-900">
              External IIT Classes & Groundwork
            </h1>
            <p className="text-xs md:text-sm text-slate-600 font-medium max-w-2xl leading-relaxed">
              Scholr does not duplicate your coaching classes — you already do 6 hours a week. Instead, it uncovers the Cambridge IGCSE foundation topics underneath so your next coaching session feels effortless!
            </p>
          </div>
          <div className="h-16 w-16 rounded-3xl bg-gradient-to-tr from-purple-500 via-indigo-500 to-amber-500 flex items-center justify-center text-3xl text-white shadow-lg shadow-purple-500/25 select-none animate-float flex-none">
            🚀
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
              className="flex flex-wrap items-center gap-3 rounded-2xl border border-amber-200/70 bg-white p-3.5 shadow-2xs transition hover:border-purple-300"
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
