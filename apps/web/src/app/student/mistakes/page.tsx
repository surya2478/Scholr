"use client";

import Link from "next/link";
import { useState } from "react";
import { BugHunter } from "@/components/BugHunter";
import { MathText } from "@/components/MathText";
import { Card, Chip, Empty, ErrorNote } from "@/components/ui";
import type { AutopsyEntry, Mistake } from "@/lib/api";
import { shortDate } from "@/lib/format";
import { tutorHref } from "@/lib/tutor";
import { useApi } from "@/lib/useApi";

const FILTERS = [
  { value: "", label: "All" },
  { value: "open", label: "Open" },
  { value: "improving", label: "Improving" },
  { value: "resolved", label: "Fixed" },
];

export default function Mistakes() {
  const [activeTab, setActiveTab] = useState<"tracker" | "bughunter" | "diary">("tracker");
  const [status, setStatus] = useState("");
  const [diaryCategory, setDiaryCategory] = useState("");
  const list = useApi<Mistake[]>(`/mistakes${status ? `?status=${status}` : ""}`);
  const autopsies = useApi<AutopsyEntry[]>("/evaluations/autopsies");

  const filteredAutopsies = (autopsies.data ?? []).filter(
    (a) => !diaryCategory || a.category === diaryCategory
  );

  return (
    <div className="space-y-6">
      {/* Friendly Header */}
      <div className="rounded-3xl border-2 border-amber-200 bg-gradient-to-br from-amber-50 via-[#FFF4E8] to-orange-50 p-6 md:p-8 shadow-sm">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="space-y-1 text-center sm:text-left">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-100 text-orange-800 text-xs font-fun font-bold border border-orange-200">
              <span>🔍</span> Feedback Loop & Anti-Trap Training
            </span>
            <h1 className="text-2xl md:text-3xl font-fun font-bold text-slate-900">
              My Mistakes Detective & Error Diary 🕵️‍♀️
            </h1>
            <p className="text-xs md:text-sm text-slate-600 font-medium max-w-xl">
              Track recurring traps in your own work, review your personal error autopsy rules, or play the Chief Examiner hunting bugs!
            </p>
          </div>
          <div className="h-16 w-16 rounded-3xl bg-gradient-to-tr from-amber-400 to-orange-500 flex items-center justify-center text-3xl text-white shadow-md select-none animate-float">
            💡
          </div>
        </div>

        {/* Tab Switcher */}
        <div className="flex flex-wrap gap-2 mt-5 pt-3 border-t border-amber-200/80">
          <button
            type="button"
            onClick={() => setActiveTab("tracker")}
            className={`px-4 py-2 rounded-2xl font-fun font-bold text-xs transition-all cursor-pointer ${
              activeTab === "tracker"
                ? "bg-orange-500 text-white shadow-xs"
                : "bg-white text-slate-600 hover:bg-orange-100/60 border border-orange-200"
            }`}
          >
            📋 My Marked Traps Tracker
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("diary")}
            className={`px-4 py-2 rounded-2xl font-fun font-bold text-xs transition-all cursor-pointer ${
              activeTab === "diary"
                ? "bg-purple-600 text-white shadow-xs"
                : "bg-white text-slate-600 hover:bg-purple-100/60 border border-purple-200"
            }`}
          >
            📔 My Personal Error Diary ({autopsies.data?.length ?? 0})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("bughunter")}
            className={`px-4 py-2 rounded-2xl font-fun font-bold text-xs transition-all cursor-pointer ${
              activeTab === "bughunter"
                ? "bg-orange-500 text-white shadow-xs"
                : "bg-white text-slate-600 hover:bg-orange-100/60 border border-orange-200"
            }`}
          >
            🔬 Chief Examiner: Bug Hunter
          </button>
        </div>
      </div>

      {activeTab === "bughunter" ? (
        <BugHunter />
      ) : activeTab === "diary" ? (
        <Card
          title="📔 My Personal Error Diary (गलती डायरी)"
          subtitle="Your own rules and takeaways diagnosed after questions where marks were lost. Reviewing these before an exam builds cognitive immunity against making them again!"
          tone="purple"
        >
          <div className="flex flex-wrap gap-2 pt-1">
            {[
              { value: "", label: "All Categories" },
              { value: "conceptual", label: "🧠 Conceptual" },
              { value: "calculation", label: "✏️ Calculation" },
              { value: "misreading", label: "🔍 Misreading" },
              { value: "strategy", label: "⏱️ Strategic" },
            ].map((f) => (
              <button
                key={f.value}
                onClick={() => setDiaryCategory(f.value)}
                className={`rounded-2xl px-3.5 py-1.5 text-xs font-fun font-bold transition-all cursor-pointer ${
                  diaryCategory === f.value
                    ? "bg-purple-600 text-white shadow-xs"
                    : "bg-purple-50/70 border border-purple-200/80 text-purple-900 hover:bg-white"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {autopsies.error ? <ErrorNote error={autopsies.error} /> : null}
          {filteredAutopsies.length === 0 && (
            <Empty>
              No error diary entries yet. When you conduct an error autopsy in Practice Lab or Tests, your personal rules will appear here! 🌟
            </Empty>
          )}

          <ul className="flex flex-col gap-3.5 pt-2">
            {filteredAutopsies.map((entry) => (
              <li
                key={entry.evaluation_id}
                className="flex flex-col gap-2.5 rounded-2xl border-2 border-purple-200/80 bg-gradient-to-br from-white via-[#FAF7FD] to-purple-50/40 p-4 shadow-2xs hover:border-purple-300 transition-colors"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-purple-100 pb-2">
                  <div className="flex items-center gap-2 text-xs">
                    {entry.objective_code && (
                      <span className="font-fun font-bold text-purple-800 bg-purple-100 px-2 py-0.5 rounded-md">
                        Topic {entry.objective_code}
                      </span>
                    )}
                    <span className="text-slate-400 font-medium">
                      Recorded on {shortDate(entry.recorded_at)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-600">
                      Scored {entry.marks_awarded} / {entry.marks_available} Marks
                    </span>
                    <Chip tone="brand">
                      {entry.category.toUpperCase()}
                    </Chip>
                  </div>
                </div>

                <div className="text-xs text-slate-600 font-medium line-clamp-2">
                  <span className="font-bold text-slate-800">Question: </span>
                  <MathText text={entry.stem} />
                </div>

                <div className="p-3 rounded-xl bg-purple-100/70 border border-purple-200 text-xs">
                  <div className="text-[10px] font-fun font-bold uppercase tracking-wider text-purple-900 mb-0.5">
                    💡 My Personal Rule for Next Time:
                  </div>
                  <div className="text-sm font-semibold text-purple-950 italic">
                    &ldquo;{entry.takeaway}&rdquo;
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      ) : (
        <Card title="Mistake Tracker" subtitle="Filter by status to target what to practice next">
        <div className="flex flex-wrap gap-2 pt-1">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setStatus(f.value)}
              className={`rounded-2xl px-4 py-1.5 text-xs font-fun font-bold transition-all cursor-pointer ${
                status === f.value
                  ? "bg-gradient-to-r from-orange-500 to-amber-500 text-white shadow-xs"
                  : "bg-amber-50/70 border border-amber-200/80 text-slate-600 hover:text-slate-900 hover:bg-white"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {list.error ? <ErrorNote error={list.error} /> : null}
        {list.data?.length === 0 && (
          <Empty>Awesome! No mistakes found in this category. Keep up the brilliant focus! 🌟</Empty>
        )}

        <ul className="flex flex-col gap-3 pt-2">
          {list.data?.map((m) => (
            <li
              key={m.id}
              className="flex flex-wrap items-start gap-3 rounded-2xl border-2 border-amber-200/70 bg-[#FFFDF9] p-4 shadow-2xs hover:border-orange-300 transition-colors"
            >
              <div className="min-w-0 flex-1 space-y-1">
                <MathText text={m.description} className="text-sm font-semibold text-slate-900" />
                <div className="text-xs text-slate-500 font-medium">
                  {m.objective_code ? (
                    <span className="font-bold text-orange-700">Topic {m.objective_code} · </span>
                  ) : (
                    ""
                  )}
                  Seen {m.occurrences} time{m.occurrences === 1 ? "" : "s"} · last on {shortDate(m.last_seen)}
                </div>
                <div className="flex flex-wrap gap-3 pt-1 text-xs font-fun font-bold">
                  {m.objective_id && (
                    <Link href={`/student/learn/topic/${m.objective_id}`} className="text-orange-600 hover:underline">
                      📘 Open the topic
                    </Link>
                  )}
                  <Link
                    href={tutorHref({
                      subjectId: m.subject_id,
                      objectiveId: m.objective_id,
                      ask: `I keep making this mistake: ${m.description} How do I avoid it?`,
                    })}
                    className="text-orange-600 hover:underline"
                  >
                    🦉 Ask the Tutor about this mistake
                  </Link>
                </div>
              </div>
              <Chip tone={m.severity === "high" ? "alert" : m.severity === "medium" ? "warn" : "neutral"}>
                {m.severity === "high" ? "High Priority ⚠️" : m.severity === "medium" ? "Medium" : "Minor"}
              </Chip>
              <Chip tone={m.status === "resolved" ? "good" : m.status === "improving" ? "brand" : "neutral"}>
                {m.status === "resolved" ? "Fixed ✓" : m.status === "improving" ? "Improving 📈" : m.status}
              </Chip>
            </li>
          ))}
        </ul>
      </Card>
      )}
    </div>
  );
}
