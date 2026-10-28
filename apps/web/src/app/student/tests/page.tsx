"use client";

import Link from "next/link";
import { useMe } from "@/components/AppShell";
import { Card, Chip, Empty, ErrorNote } from "@/components/ui";
import type { AssessmentBrief } from "@/lib/api";
import { KIND_LABELS, shortDate } from "@/lib/format";
import { useApi } from "@/lib/useApi";

const STATUS_TONE: Record<string, "neutral" | "brand" | "good"> = {
  draft: "neutral",
  in_progress: "brand",
  submitted: "good",
  evaluated: "good",
};
const STATUS_LABEL: Record<string, string> = {
  draft: "Not started",
  in_progress: "In progress",
  submitted: "Submitted",
  evaluated: "Marked",
  abandoned: "Cancelled",
};

export default function Tests() {
  const me = useMe();
  const list = useApi<AssessmentBrief[]>("/assessments");
  const names = Object.fromEntries((me?.student?.enrollments ?? []).map((e) => [e.subject_id, e.subject_name]));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-3xl bg-gradient-to-r from-[#0B1528] via-[#13294B] to-[#1E3A8A] p-6 md:p-8 text-white shadow-xl">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="space-y-2 text-center sm:text-left">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/10 text-emerald-300 font-mono text-xs font-bold border border-white/15">
              <span>📋</span> CAMBRIDGE BENCHMARK &amp; RETENTION TESTS
            </span>
            <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
              Assigned Tests &amp; Study Benchmarks
            </h1>
            <p className="text-xs md:text-sm text-slate-300 font-medium max-w-xl leading-relaxed">
              Baseline, post-topic, and retention assessments designed to measure your true independent exam readiness.
            </p>
          </div>
          <div className="h-14 w-14 rounded-2xl bg-white/10 border border-white/15 flex items-center justify-center font-mono text-lg font-extrabold text-emerald-300 flex-none">
            TS
          </div>
        </div>
      </div>

      <Card
        title="Assigned Assessment Papers"
        subtitle="During a formal study test, AI hints are paused to measure authentic exam condition performance"
      >
        {list.error ? <ErrorNote error={list.error} /> : null}
        {list.data?.length === 0 && (
          <Empty>No assigned tests pending right now. You can build a custom mock paper in Mock Examinations.</Empty>
        )}
        <ul className="flex flex-col gap-3 pt-1">
          {list.data?.map((a) => (
            <li key={a.id}>
              <Link
                href={`/student/tests/${a.id}`}
                className="flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200/90 bg-white p-4 hover:border-blue-500 hover:bg-blue-50/20 transition-all shadow-2xs"
              >
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-extrabold text-slate-900">
                    {names[a.subject_id] ?? "Cambridge Subject"} · {KIND_LABELS[a.kind] ?? a.kind}
                    {a.form_code ? ` (Form ${a.form_code})` : ""}
                  </div>
                  <div className="font-mono text-xs text-slate-500 font-medium mt-0.5">
                    {a.total_marks} marks available · Created {shortDate(a.created_at)}
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
