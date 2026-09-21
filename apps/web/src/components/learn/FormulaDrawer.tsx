"use client";

import { useState } from "react";
import { MathText } from "@/components/MathText";
import type { Lesson } from "@/lib/api";

export function FormulaDrawer({ lesson }: { lesson: Lesson | null }) {
  const [isOpen, setIsOpen] = useState(false);

  if (!lesson || (lesson.key_terms.length === 0 && lesson.pitfalls.length === 0)) {
    return null;
  }

  const termsCount = lesson.key_terms.length;
  const pitfallsCount = lesson.pitfalls.length;

  return (
    <>
      {/* Floating Trigger Button */}
      <aside aria-label="Quick reference drawer" className="fixed bottom-5 right-5 z-40">
        <button
          onClick={() => setIsOpen(true)}
          className="flex items-center gap-2 rounded-full border border-orange-300 bg-white/95 px-4 py-2.5 text-xs font-fun font-bold text-orange-800 shadow-lg backdrop-blur-xs transition hover:bg-orange-50 active:scale-95"
          title="Open Formulas and Key Terms cheat-sheet"
        >
          <span className="text-sm">📐</span>
          <span>Formulas &amp; Terms</span>
          <span className="rounded-full bg-orange-100 px-1.5 py-0.2 text-[10px] font-extrabold text-orange-700">
            {termsCount + pitfallsCount}
          </span>
        </button>
      </aside>

      {/* Backdrop & Drawer Panel */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/30 backdrop-blur-2xs transition-opacity animate-in fade-in">
          {/* Click outside to close */}
          <div className="flex-1" onClick={() => setIsOpen(false)} />

          <div className="flex h-full w-full max-w-md flex-col bg-white p-5 shadow-2xl overflow-y-auto">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <span className="text-lg">📐</span>
                <h2 className="font-fun text-base font-bold text-slate-900">
                  Formulas &amp; Reference
                </h2>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                ✕
              </button>
            </div>

            <p className="mt-2 text-xs text-slate-500">
              Quickly check definitions, identities, and examiner pitfalls without losing your place.
            </p>

            <div className="mt-4 flex flex-col gap-5">
              {/* Key Terms */}
              {lesson.key_terms.length > 0 && (
                <div className="flex flex-col gap-2">
                  <h3 className="font-fun text-xs font-bold uppercase tracking-wider text-blue-800">
                    Key Terms &amp; Definitions ({termsCount})
                  </h3>
                  <div className="divide-y divide-slate-100 rounded-xl border border-blue-100 bg-blue-50/40 p-3">
                    {lesson.key_terms.map((t, i) => (
                      <div key={i} className="py-2 first:pt-0 last:pb-0 text-xs">
                        <span className="font-bold text-slate-900">{t.term}: </span>
                        <span className="text-slate-700">
                          <MathText text={t.meaning} />
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Pitfalls */}
              {lesson.pitfalls.length > 0 && (
                <div className="flex flex-col gap-2">
                  <h3 className="font-fun text-xs font-bold uppercase tracking-wider text-amber-800">
                    Watch Out For ({pitfallsCount})
                  </h3>
                  <ul className="space-y-1.5 rounded-xl border border-amber-200 bg-amber-50/50 p-3 text-xs text-slate-700">
                    {lesson.pitfalls.map((p, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="text-amber-600 font-bold shrink-0">⚠️</span>
                        <MathText text={p} />
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Bottom Dismiss */}
            <div className="mt-auto pt-6">
              <button
                onClick={() => setIsOpen(false)}
                className="w-full rounded-xl bg-slate-100 py-2.5 text-xs font-fun font-bold text-slate-700 hover:bg-slate-200"
              >
                Back to topic
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
