"use client";

import Link from "next/link";
import { useState } from "react";
import { MathText } from "@/components/MathText";
import type { ExamLevel, Lesson, ObjectiveCard, SubjectCard } from "@/lib/api";

type Connection = {
  objective_id: string;
  objective_code: string;
  statement: string;
  subject_name: string;
  concept: string;
  practicable: boolean;
};

export function DualLensView({
  subject,
  objective,
  connections,
  lesson,
  examLevel,
}: {
  subject: SubjectCard;
  objective: ObjectiveCard;
  connections: Connection[];
  lesson?: Lesson | null;
  examLevel?: ExamLevel | null;
}) {
  const isCurrentIit = subject.name.toLowerCase().includes("iit");
  const [activeLens, setActiveLens] = useState<"cambridge" | "iit">(isCurrentIit ? "iit" : "cambridge");

  const iitConnections = connections.filter((c) => c.subject_name.toLowerCase().includes("iit"));
  const igcseConnections = connections.filter((c) => !c.subject_name.toLowerCase().includes("iit"));

  if (connections.length === 0) {
    return null;
  }

  const sharedConcepts = Array.from(new Set(connections.map((c) => c.concept)));
  const how = examLevel?.how_examined ?? null;
  const topPitfall = lesson?.pitfalls?.[0] ?? null;
  const topTerm = lesson?.key_terms?.[0] ?? null;

  return (
    <div className="rounded-3xl border-2 border-indigo-200 bg-gradient-to-br from-[#FAF5FF] via-white to-[#F0F4FF] p-5 md:p-6 shadow-sm space-y-4">
      {/* Header with Dual Lens Switcher */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-indigo-100 pb-4">
        <div className="space-y-0.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xl">🔗</span>
            <span className="font-fun font-bold text-slate-900 text-base">
              Cambridge IGCSE ↔ IIT Foundation Concept Bridge
            </span>
            {sharedConcepts.slice(0, 2).map((concept) => (
              <span
                key={concept}
                className="rounded-full bg-indigo-100 px-2.5 py-0.5 text-[11px] font-fun font-bold text-indigo-800 border border-indigo-200"
              >
                {concept}
              </span>
            ))}
          </div>
          <p className="text-xs text-slate-600 font-medium">
            See how <strong>{objective.code} {objective.statement}</strong> connects across your school syllabus and coaching classes.
          </p>
        </div>

        {/* Lens Toggle */}
        <div className="flex items-center bg-indigo-100/80 p-1 rounded-2xl border border-indigo-200 self-stretch sm:self-auto">
          <button
            type="button"
            onClick={() => setActiveLens("cambridge")}
            className={`flex-1 sm:flex-initial px-3.5 py-1.5 rounded-xl font-fun font-bold text-xs transition-all cursor-pointer ${
              activeLens === "cambridge"
                ? "bg-white text-indigo-950 shadow-2xs"
                : "text-indigo-700 hover:text-indigo-900"
            }`}
          >
            🇬🇧 Cambridge IGCSE View
          </button>
          <button
            type="button"
            onClick={() => setActiveLens("iit")}
            className={`flex-1 sm:flex-initial px-3.5 py-1.5 rounded-xl font-fun font-bold text-xs transition-all cursor-pointer ${
              activeLens === "iit"
                ? "bg-white text-indigo-950 shadow-2xs"
                : "text-indigo-700 hover:text-indigo-900"
            }`}
          >
            🇮🇳 IIT Foundation Bridge
          </button>
        </div>
      </div>

      {/* Lens 1: Topic-Specific Cambridge Perspective */}
      {activeLens === "cambridge" && (
        <div className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <div className="p-3.5 rounded-2xl bg-white border border-indigo-100 space-y-1 shadow-2xs">
              <span className="font-fun font-bold text-indigo-950 block">
                📋 How Cambridge Tests {objective.code}
              </span>
              {how ? (
                <p className="text-slate-700 leading-relaxed">
                  Appeared <strong>{how.asked}×</strong> in your bank ({how.years.join("–")}) on{" "}
                  <strong>{how.papers.join(", ")}</strong> for{" "}
                  <strong>
                    {how.marks_min === how.marks_max ? how.marks_min : `${how.marks_min}–${how.marks_max}`} marks
                  </strong>
                  {how.command_words.length > 0 ? ` (command words: ${how.command_words.join(", ")})` : ""}.
                </p>
              ) : (
                <p className="text-slate-600 leading-relaxed">
                  Assessed on structured working, precise terminology, and explicit step-by-step reasoning in{" "}
                  <strong>{subject.name}</strong>.
                </p>
              )}
            </div>

            <div className="p-3.5 rounded-2xl bg-white border border-indigo-100 space-y-1 shadow-2xs">
              <span className="font-fun font-bold text-indigo-950 block">
                📘 Core Concept Anchor
              </span>
              {topTerm ? (
                <div className="text-slate-700 leading-relaxed">
                  <strong>{topTerm.term}: </strong>
                  <MathText text={topTerm.meaning} />
                </div>
              ) : (
                <p className="text-slate-600 leading-relaxed">
                  Shared concept: <strong>{sharedConcepts.join(", ")}</strong>. Master the definition and standard method before speeding up.
                </p>
              )}
            </div>

            <div className="p-3.5 rounded-2xl bg-amber-50/80 border border-slate-200 space-y-1 shadow-2xs">
              <span className="font-fun font-bold text-amber-900 block">
                ⚠️ Topic Watch-Out
              </span>
              {topPitfall ? (
                <div className="text-amber-950 leading-relaxed">
                  <MathText text={topPitfall} />
                </div>
              ) : (
                <p className="text-amber-950 leading-relaxed">
                  Write every intermediate transformation clearly so method marks ($M$) are secured even if a numerical slip occurs.
                </p>
              )}
            </div>
          </div>

          {igcseConnections.length > 0 && (
            <div className="space-y-2 pt-1">
              <div className="text-xs font-fun font-bold text-indigo-950">
                Connected Cambridge IGCSE Topics:
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {igcseConnections.map((conn) => (
                  <Link
                    key={conn.objective_id}
                    href={`/student/learn/topic/${conn.objective_id}`}
                    className="p-3 rounded-xl bg-white border border-indigo-200/80 hover:border-indigo-400 transition flex items-center justify-between shadow-2xs group"
                  >
                    <div className="space-y-0.5 min-w-0">
                      <div className="text-xs font-bold text-slate-900 group-hover:text-indigo-600 transition-colors truncate">
                        {conn.subject_name} · {conn.objective_code} {conn.statement}
                      </div>
                      <div className="text-[11px] text-slate-500">
                        Shared concept: <strong>{conn.concept}</strong>
                      </div>
                    </div>
                    <span className="text-xs font-bold text-indigo-600 flex-none ml-2">Open →</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Lens 2: IIT Foundation Bridge */}
      {activeLens === "iit" && (
        <div className="space-y-3">
          <div className="p-3.5 rounded-2xl bg-purple-50/90 border border-purple-200 text-xs text-purple-950 space-y-1">
            <div className="font-fun font-bold text-purple-900">
              🚀 How Coaching Builds on {objective.code} ({sharedConcepts.join(", ")})
            </div>
            <p className="leading-relaxed">
              Your AhaGuru IIT Foundation classes rely on <strong>{sharedConcepts.join(" and ")}</strong> as assumed ground. Making sure this IGCSE foundation is rock-solid lets you focus on multi-step synthesis during your coaching tests.
            </p>
          </div>

          {iitConnections.length > 0 ? (
            <div className="space-y-2">
              <div className="text-xs font-fun font-bold text-purple-950">
                Linked IIT Foundation Lessons:
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {iitConnections.map((conn) => (
                  <Link
                    key={conn.objective_id}
                    href={`/student/learn/topic/${conn.objective_id}`}
                    className="p-3 rounded-xl bg-white border border-purple-200 hover:border-purple-400 transition flex items-center justify-between shadow-2xs group"
                  >
                    <div className="space-y-0.5 min-w-0">
                      <div className="text-xs font-bold text-slate-900 group-hover:text-purple-700 transition-colors truncate">
                        {conn.subject_name}: {conn.objective_code} {conn.statement}
                      </div>
                      <div className="text-[11px] text-slate-500">
                        Concept link: <strong>{conn.concept}</strong>
                      </div>
                    </div>
                    <span className="text-xs font-bold text-purple-700 flex-none ml-2">IIT Lesson →</span>
                  </Link>
                ))}
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {igcseConnections.map((conn) => (
                <Link
                  key={conn.objective_id}
                  href={`/student/learn/topic/${conn.objective_id}`}
                  className="p-3 rounded-xl bg-white border border-purple-200 hover:border-purple-400 transition flex items-center justify-between shadow-2xs group"
                >
                  <div className="space-y-0.5 min-w-0">
                    <div className="text-xs font-bold text-slate-900 group-hover:text-purple-700 transition-colors truncate">
                      {conn.subject_name}: {conn.objective_code} {conn.statement}
                    </div>
                    <div className="text-[11px] text-slate-500">
                      IGCSE prerequisite: <strong>{conn.concept}</strong>
                    </div>
                  </div>
                  <span className="text-xs font-bold text-purple-700 flex-none ml-2">Revise Ground →</span>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
