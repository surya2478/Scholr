"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { TryQuestion } from "@/components/learn/TryQuestion";
import { Card, Chip, Empty, ErrorNote } from "@/components/ui";
import type { DailyPractice } from "@/lib/api";
import { tutorHref } from "@/lib/tutor";
import { useApi } from "@/lib/useApi";

const SPRINT_SECONDS = 180; // 3 minutes

export default function MemoryBoostPage() {
  const set = useApi<DailyPractice>("/practice/daily");
  const data = set.data;

  const [timeLeft, setTimeLeft] = useState<number>(SPRINT_SECONDS);
  const [timerActive, setTimerActive] = useState<boolean>(true);
  const [answeredIds, setAnsweredIds] = useState<Set<string>>(new Set());

  // Countdown timer
  useEffect(() => {
    if (!timerActive) return;
    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          setTimerActive(false);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [timerActive]);

  // Only the questions today's set chose because a topic is due for spaced revision (planner reason
  // "retention_*": her retention risk, from her own record). No other question is passed off as one.
  const due = (data?.items ?? []).filter((it) => it.reason_code.startsWith("retention"));
  const todo = due.filter((it) => it.status === "to_do");
  const items = (todo.length > 0 ? todo : due).slice(0, 2);

  // No clock when nothing is due.
  useEffect(() => {
    if (data && items.length === 0) setTimerActive(false);
  }, [data, items.length]);

  const allCompleted = items.length > 0 && items.every((it) => answeredIds.has(it.item_id));

  const minutes = Math.floor(timeLeft / 60);
  const seconds = timeLeft % 60;
  const progressPercent = Math.round(((SPRINT_SECONDS - timeLeft) / SPRINT_SECONDS) * 100);

  function handleResetSprint() {
    setTimeLeft(SPRINT_SECONDS);
    setTimerActive(true);
    setAnsweredIds(new Set());
  }

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      {/* Sprint Header & Timer Banner */}
      <div className="rounded-3xl border-2 border-purple-300 bg-gradient-to-r from-purple-50 via-white to-indigo-50 p-6 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-2xl">⚡</span>
              <h1 className="text-xl md:text-2xl font-fun font-bold text-purple-950">
                3-Minute Memory Boost
              </h1>
            </div>
            <p className="text-xs text-slate-600 font-medium">
              Up to 2 quick questions on topics that are due for revision, so you recall them before they fade.
            </p>
          </div>

          {/* Clock Widget */}
          <div className="flex items-center gap-3 bg-purple-900 text-white px-4 py-2.5 rounded-2xl shadow-md self-stretch sm:self-auto justify-center">
            <span className="text-xl animate-pulse">⏱️</span>
            <div>
              <div className="text-[10px] font-fun font-bold uppercase tracking-wider text-purple-300">
                Sprint Clock
              </div>
              <div className="text-xl font-mono font-extrabold">
                {String(minutes).padStart(2, "0")}:{String(seconds).padStart(2, "0")}
              </div>
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="space-y-1">
          <div className="h-2.5 w-full bg-purple-100 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-1000 ${
                timeLeft <= 30 ? "bg-rose-500 animate-pulse" : "bg-purple-600"
              }`}
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <div className="flex justify-between text-[11px] text-slate-400 font-medium">
            <span>0:00</span>
            <span>Target: 2 Questions in 3:00</span>
            <span>3:00</span>
          </div>
        </div>
      </div>

      {allCompleted && (
        <div className="p-6 rounded-3xl border-2 border-emerald-300 bg-emerald-50 text-center space-y-3 shadow-md animate-in fade-in zoom-in-95">
          <span className="text-4xl">🎉</span>
          <h2 className="text-xl font-fun font-bold text-emerald-950">
            Memory Boost Sprint Complete!
          </h2>
          <p className="text-xs text-emerald-800 font-medium max-w-md mx-auto">
            Brilliant work! You reinforced 2 key topics in under 3 minutes, halting the Ebbinghaus forgetting curve.
          </p>
          <div className="pt-2 flex flex-wrap justify-center gap-3">
            <button
              type="button"
              onClick={handleResetSprint}
              className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-fun font-bold text-xs shadow-md transition-all cursor-pointer"
            >
              ⚡ Run Another Sprint
            </button>
            <Link
              href="/student"
              className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-fun font-bold text-xs shadow-md transition-all"
            >
              Back to Dashboard →
            </Link>
            <Link
              href="/student/practice/daily"
              className="px-4 py-2 rounded-xl bg-white hover:bg-emerald-100 text-emerald-900 border border-emerald-300 font-fun font-bold text-xs transition-all"
            >
              Finish Today&apos;s Full Set
            </Link>
          </div>
        </div>
      )}

      {set.error ? <ErrorNote error={set.error} /> : null}
      {set.loading && <p className="text-sm text-slate-500 text-center py-6">Loading your revision questions…</p>}
      
      {data && items.length === 0 && (
        <div className="rounded-3xl border border-purple-200 bg-white p-6 text-center space-y-3">
          <span className="text-3xl">🌟</span>
          <h3 className="font-fun font-bold text-slate-800">Nothing is due for revision today</h3>
          <p className="text-xs text-slate-600 max-w-md mx-auto">
            None of today&apos;s questions are on topics due for revision. Today&apos;s set and the Practice page have more questions.
          </p>
          <div className="pt-2 flex justify-center gap-3">
            <Link
              href="/student/practice"
              className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-fun font-bold text-xs shadow-md"
            >
              Open Practice Lab →
            </Link>
            <Link
              href="/student/learn"
              className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 font-fun font-bold text-xs"
            >
              Browse Syllabus Topics
            </Link>
          </div>
        </div>
      )}

      {/* The 2 Sprint Questions */}
      <div className="space-y-5">
        {items.map((item, index) => (
          <Card key={item.item_id} tone="purple">
            <div className="flex flex-wrap items-start justify-between gap-2 border-b border-purple-100 pb-3">
              <div className="flex flex-col gap-0.5">
                <span className="text-xs font-semibold text-purple-800">
                  Boost Question #{index + 1} · {item.subject_name}
                </span>
                <span className="text-sm font-fun font-bold text-slate-900">
                  {item.objective_code} {item.objective_statement}
                </span>
                <span className="text-xs text-slate-500 font-medium">{item.reason}</span>
              </div>
              <Chip tone={answeredIds.has(item.item_id) ? "good" : "brand"}>
                {answeredIds.has(item.item_id) ? "Answered ✓" : `${item.marks} Marks`}
              </Chip>
            </div>

            <div className="pt-3">
              <TryQuestion
                startOpen={true}
                item={{
                  id: item.item_id,
                  source_ref: item.source_ref,
                  label: item.label,
                  marks: item.marks,
                  command_word: null,
                }}
                askHref={(q) =>
                  tutorHref({
                    subjectId: item.subject_id,
                    objectiveId: item.objective_id,
                    about: item.objective_statement,
                    ask: q,
                  })
                }
                onAnswered={() => {
                  setAnsweredIds((prev) => new Set(prev).add(item.item_id));
                  void set.reload();
                }}
              />
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
