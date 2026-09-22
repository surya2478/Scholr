"use client";

import Link from "next/link";
import { useState } from "react";
import { MathText } from "@/components/MathText";
import type { ObjectiveCard, SubjectCard } from "@/lib/api";

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
}: {
  subject: SubjectCard;
  objective: ObjectiveCard;
  connections: Connection[];
}) {
  const [activeLens, setActiveLens] = useState<"cambridge" | "iit">("cambridge");

  const iitConnections = connections.filter((c) =>
    c.subject_name.toLowerCase().includes("iit")
  );
  const igcseConnections = connections.filter((c) =>
    c.subject_name.toLowerCase().includes("cambridge") ||
    c.subject_name.toLowerCase().includes("igcse")
  );

  const isCurrentIit = subject.name.toLowerCase().includes("iit");
  const hasDualCurriculum = isCurrentIit
    ? igcseConnections.length > 0
    : iitConnections.length > 0;

  if (!hasDualCurriculum && connections.length === 0) {
    return null;
  }

  return (
    <div className="rounded-3xl border-2 border-indigo-200 bg-gradient-to-br from-[#FAF5FF] via-white to-[#F0F4FF] p-5 md:p-6 shadow-sm space-y-4">
      {/* Header with Dual Lens Switcher */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-indigo-100 pb-4">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <span className="text-xl">⚡</span>
            <span className="font-fun font-bold text-slate-900 text-base">
              Dual-Lens Concept Transformer
            </span>
            <span className="rounded-full bg-indigo-100 px-2.5 py-0.5 text-[11px] font-fun font-bold text-indigo-800 border border-indigo-200">
              Cross-Curriculum
            </span>
          </div>
          <p className="text-xs text-slate-600 font-medium">
            Switch your mental framework between Cambridge step-marks and IIT competitive speed.
          </p>
        </div>

        {/* Lens Toggle */}
        <div className="flex items-center bg-indigo-100/80 p-1 rounded-2xl border border-indigo-200 self-stretch sm:self-auto">
          <button
            type="button"
            onClick={() => setActiveLens("cambridge")}
            className={`flex-1 sm:flex-initial px-3.5 py-1.5 rounded-xl font-fun font-bold text-xs transition-all cursor-pointer ${
              activeLens === "cambridge"
                ? "bg-white text-indigo-950 shadow-2xs scale-102"
                : "text-indigo-700 hover:text-indigo-900"
            }`}
          >
            🇬🇧 Cambridge Lens
          </button>
          <button
            type="button"
            onClick={() => setActiveLens("iit")}
            className={`flex-1 sm:flex-initial px-3.5 py-1.5 rounded-xl font-fun font-bold text-xs transition-all cursor-pointer ${
              activeLens === "iit"
                ? "bg-white text-indigo-950 shadow-2xs scale-102"
                : "text-indigo-700 hover:text-indigo-900"
            }`}
          >
            🇮🇳 IIT Foundation Lens
          </button>
        </div>
      </div>

      {/* Lens 1: Cambridge Perspective */}
      {activeLens === "cambridge" && (
        <div className="space-y-3 animate-fadeIn">
          <div className="p-3.5 rounded-2xl bg-amber-50/80 border border-amber-200 text-xs text-amber-950 space-y-1.5">
            <div className="flex items-center gap-1.5 font-fun font-bold text-amber-900">
              <span>🎯</span> Cambridge Extended Examination Rules
            </div>
            <p className="leading-relaxed">
              Cambridge examiners award marks for <strong>explicit method presentation</strong>. Even if your final calculation has a slip, full method marks ($M$) and bonus marks ($B$) are protected as long as you show each algebraic transformation.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-xs">
            <div className="p-3 rounded-xl bg-white border border-indigo-100 space-y-1">
              <span className="font-fun font-bold text-indigo-900 block">📝 Method Marks (M)</span>
              <p className="text-slate-600 text-[11px] leading-relaxed">
                State formulas before substituting numbers. Never jump straight to the answer.
              </p>
            </div>
            <div className="p-3 rounded-xl bg-white border border-indigo-100 space-y-1">
              <span className="font-fun font-bold text-indigo-900 block">📐 Exact Accuracy (A)</span>
              <p className="text-slate-600 text-[11px] leading-relaxed">
                Give non-exact answers to 3 significant figures and angles to 1 decimal place.
              </p>
            </div>
            <div className="p-3 rounded-xl bg-white border border-indigo-100 space-y-1">
              <span className="font-fun font-bold text-indigo-900 block">⚖️ Non-Calc Discipline</span>
              <p className="text-slate-600 text-[11px] leading-relaxed">
                Paper 2 forbids calculators. Keep surds, $\pi$, and fractions in simplest exact form.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Lens 2: IIT Perspective */}
      {activeLens === "iit" && (
        <div className="space-y-3 animate-fadeIn">
          <div className="p-3.5 rounded-2xl bg-purple-50/80 border border-purple-200 text-xs text-purple-950 space-y-1.5">
            <div className="flex items-center gap-1.5 font-fun font-bold text-purple-900">
              <span>🚀</span> IIT Foundation Problem Solving Heuristics
            </div>
            <p className="leading-relaxed">
              IIT coaching tests <strong>multi-concept synthesis and speed</strong>. Instead of writing long standard steps, look for symmetries, invariant quantities, extreme cases (e.g., setting variables to $0$ or $1$), and substitution tricks.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-xs">
            <div className="p-3 rounded-xl bg-white border border-purple-100 space-y-1">
              <span className="font-fun font-bold text-purple-900 block">⚡ Invariant Spotting</span>
              <p className="text-slate-600 text-[11px] leading-relaxed">
                Identify what remains constant (momentum, energy, geometric angles) across changes.
              </p>
            </div>
            <div className="p-3 rounded-xl bg-white border border-purple-100 space-y-1">
              <span className="font-fun font-bold text-purple-900 block">🔗 Multi-Concept Chain</span>
              <p className="text-slate-600 text-[11px] leading-relaxed">
                One question usually links 2 or 3 chapters together. Break it into its dependencies.
              </p>
            </div>
            <div className="p-3 rounded-xl bg-white border border-purple-100 space-y-1">
              <span className="font-fun font-bold text-purple-900 block">⏱️ 90-Second Heuristic</span>
              <p className="text-slate-600 text-[11px] leading-relaxed">
                If straightforward algebra takes more than 5 lines, a shortcut or factorization exists.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Cross-Curriculum De-lamination Tree */}
      {isCurrentIit && igcseConnections.length > 0 && (
        <div className="space-y-2 pt-1 border-t border-indigo-100">
          <div className="text-xs font-fun font-bold text-indigo-950 flex items-center gap-1.5">
            <span>🧩</span>
            <span>Foundational Cambridge Building Blocks (De-lamination)</span>
          </div>
          <p className="text-xs text-slate-600">
            This advanced IIT coaching lesson rests on these core Cambridge IGCSE topics. Warm up with these first:
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {igcseConnections.map((conn) => (
              <Link
                key={conn.objective_id}
                href={`/student/learn/topic/${conn.objective_id}`}
                className="p-3 rounded-xl bg-white border border-indigo-200/80 hover:border-indigo-400 transition flex items-center justify-between shadow-2xs group"
              >
                <div className="space-y-0.5">
                  <div className="text-xs font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
                    {conn.objective_code} {conn.statement}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Shared Concept: <strong>{conn.concept}</strong>
                  </div>
                </div>
                <span className="text-xs font-bold text-indigo-600 flex-none ml-2">Practice →</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {!isCurrentIit && iitConnections.length > 0 && (
        <div className="space-y-2 pt-1 border-t border-indigo-100">
          <div className="text-xs font-fun font-bold text-indigo-950 flex items-center gap-1.5">
            <span>🚀</span>
            <span>Connected IIT Foundation Extension</span>
          </div>
          <p className="text-xs text-slate-600">
            See how your external coaching takes this exact concept to competitive Grade 9/10 level:
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {iitConnections.map((conn) => (
              <Link
                key={conn.objective_id}
                href={`/student/learn/topic/${conn.objective_id}`}
                className="p-3 rounded-xl bg-white border border-indigo-200/80 hover:border-indigo-400 transition flex items-center justify-between shadow-2xs group"
              >
                <div className="space-y-0.5">
                  <div className="text-xs font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
                    {conn.subject_name}: {conn.objective_code} {conn.statement}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Shared Concept: <strong>{conn.concept}</strong>
                  </div>
                </div>
                <span className="text-xs font-bold text-indigo-600 flex-none ml-2">Open IIT Topic →</span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
