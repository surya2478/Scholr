"use client";

import type { Topic } from "@/lib/api";

// What this topic page is made of, and roughly how long it takes (docs/STUDENT-APP.md AC-U13). Every number
// comes from the API, which computes it from the page's own content; a part is ticked only where her record
// says she did it. It is also the page's map: each part jumps to its section, and the bar follows her down the
// page, so practice and past mistakes are never something she has to scroll to find. No score, no streak.
export function TopicSteps({
  steps,
  minutes,
  links = [],
}: {
  steps: Topic["steps"];
  minutes: number;
  // Parts of the page that are reference, not work: they carry no time and no tick, only a way to reach them.
  links?: { key: string; label: string }[];
}) {
  if (steps.length === 0) return null;
  const done = steps.filter((s) => s.done).length;
  const current = steps.findIndex((s) => !s.done);
  const left = steps.filter((s) => !s.done).reduce((total, s) => total + s.minutes, 0);

  return (
    <div className="sticky top-2 z-20 flex flex-col gap-2 rounded-2xl border border-amber-200 bg-white/95 p-3 shadow-sm backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-bold text-slate-700">
          {done === steps.length
            ? `You've done all ${steps.length} ${steps.length === 1 ? "part" : "parts"} of this topic`
            : `Part ${current + 1} of ${steps.length}`}
        </span>
        <span className="text-[11px] font-semibold text-slate-500">
          {done === steps.length ? `about ${minutes} min in total` : `about ${left} min left`}
        </span>
      </div>
      <ol className="flex flex-wrap gap-1.5">
        {steps.map((step, i) => (
          <li key={step.key}>
            <a
              href={`#part-${step.key}`}
              className={`flex items-center gap-1.5 rounded-xl px-2.5 py-1 text-[11px] font-semibold transition-colors ${
                step.done
                  ? "bg-emerald-50 text-emerald-800 hover:bg-emerald-100"
                  : i === current
                    ? "bg-orange-100 text-orange-900 hover:bg-orange-200"
                    : "bg-slate-100 text-slate-500 hover:bg-slate-200"
              }`}
            >
              <span aria-hidden>{step.done ? "✓" : i + 1}</span>
              {step.label}
              <span className="font-normal opacity-70">· {step.minutes} min</span>
            </a>
          </li>
        ))}
        {links.map((link) => (
          <li key={link.key}>
            <a
              href={`#part-${link.key}`}
              className="flex items-center gap-1.5 rounded-xl px-2.5 py-1 text-[11px] font-semibold text-slate-500 hover:bg-slate-100"
            >
              {link.label}
            </a>
          </li>
        ))}
      </ol>
    </div>
  );
}
