"use client";

import Link from "next/link";
import { useMe } from "@/components/AppShell";
import { Card, Chip, Empty, ErrorNote } from "@/components/ui";
import type { AssessmentBrief } from "@/lib/api";
import { KIND_LABELS, shortDate } from "@/lib/format";
import { useApi } from "@/lib/useApi";

const STATUS_TONE: Record<string, "neutral" | "brand" | "good"> = { draft: "neutral", in_progress: "brand", submitted: "good", evaluated: "good" };
const STATUS_LABEL: Record<string, string> = { draft: "Not started", in_progress: "In progress", submitted: "Submitted", evaluated: "Marked", abandoned: "Cancelled" };

export default function Tests() {
  const me = useMe();
  const list = useApi<AssessmentBrief[]>("/assessments");
  const names = Object.fromEntries((me?.student?.enrollments ?? []).map((e) => [e.subject_id, e.subject_name]));

  return (
    <div className="space-y-6">
      {/* Friendly Header */}
      <div className="rounded-3xl border-2 border-amber-200 bg-gradient-to-br from-amber-50 via-[#FFF4E8] to-orange-50 p-6 md:p-8 shadow-sm">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="space-y-1 text-center sm:text-left">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-100 text-orange-800 text-xs font-fun font-bold border border-orange-200">
              <span>📝</span> Cambridge Study Tests
            </span>
            <h1 className="text-2xl md:text-3xl font-fun font-bold text-slate-900">
              My Practice Tests & Quizzes
            </h1>
            <p className="text-xs md:text-sm text-slate-600 font-medium max-w-xl">
              Baseline, post, and retention tests set to benchmark your Cambridge exam readiness.
            </p>
          </div>
          <div className="h-16 w-16 rounded-3xl bg-gradient-to-tr from-amber-400 to-orange-500 flex items-center justify-center text-3xl text-white shadow-md select-none animate-float">
            📋
          </div>
        </div>
      </div>

      <Card title="Assigned Tests" subtitle="During a study test, hints from the Tutor are paused to measure true independence">
        {list.error ? <ErrorNote error={list.error} /> : null}
        {list.data?.length === 0 && (
          <Empty>No tests set right now. Continue your daily practice in the lab! 🌟</Empty>
        )}
        <ul className="flex flex-col gap-3 pt-1">
          {list.data?.map((a) => (
            <li key={a.id}>
              <Link
                href={`/student/tests/${a.id}`}
                className="flex flex-wrap items-center gap-3 rounded-2xl border-2 border-amber-200/70 bg-[#FFFDF9] p-4 hover:border-orange-400 hover:bg-orange-50/40 transition-all shadow-2xs hover:scale-101"
              >
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-fun font-bold text-slate-900">
                    {names[a.subject_id] ?? "Cambridge Subject"} · {KIND_LABELS[a.kind] ?? a.kind}
                    {a.form_code ? ` (Form ${a.form_code})` : ""}
                  </div>
                  <div className="text-xs text-slate-500 font-medium mt-0.5">
                    {a.total_marks} marks available · created on {shortDate(a.created_at)}
                  </div>
                </div>
                <Chip tone={STATUS_TONE[a.status] ?? "neutral"}>
                  {STATUS_LABEL[a.status] ?? a.status}
                </Chip>
              </Link>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
