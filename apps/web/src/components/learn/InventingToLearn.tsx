"use client";

import { useState } from "react";
import { MathText } from "@/components/MathText";
import { Button, Card, Chip } from "@/components/ui";

type MysteryCase = {
  id: string;
  keywords: string[];
  title: string;
  subject: string;
  historical_inventor: string;
  year: string;
  target_concept: string;
  formal_formula: string;
  mystery_story: string;
  case_data: { label: string; values: string; note: string }[];
  intuitive_failure_point: string;
  discovery_reveal: string;
};

const MYSTERY_CASES: MysteryCase[] = [
  {
    id: "invent-spread",
    keywords: ["mean", "median", "average", "spread", "interquartile", "cumulative", "statistics"],
    title: "The Mystery of the Identical Averages",
    subject: "Mathematics (0580 & IIT)",
    historical_inventor: "Karl Pearson",
    year: "1893",
    target_concept: "Measuring Spread & Consistency",
    formal_formula: "\\text{IQR} = Q_3 - Q_1 \\quad \\text{or} \\quad \\sigma = \\sqrt{\\frac{\\sum (x - \\mu)^2}{N}}",
    mystery_story:
      "Two students (Rohan and Ananya) applied for a selective scholarship. Both sat 5 exam papers, " +
      "and both achieved an identical mean average score of 70%. But look at their individual papers:",
    case_data: [
      { label: "Rohan's Marks", values: "70%, 70%, 70%, 70%, 70%", note: "Mean = 70%" },
      { label: "Ananya's Marks", values: "40%, 55%, 70%, 85%, 100%", note: "Mean = 70%" },
    ],
    intuitive_failure_point:
      "If you only look at the Mean or Median, both candidates look identical! " +
      "What if you measure spread by subtracting each mark from 70? " +
      "(-30) + (-15) + 0 + 15 + 30 = 0! " +
      "The positive and negative deviations completely cancel each other out!",
    discovery_reveal:
      "Statisticians realized you must either measure the middle 50% range (Interquartile Range $Q_3 - Q_1$) or square each distance from the mean " +
      "so negatives become positive ($(-30)^2 = 900$), find their average, then take the square root.",
  },
  {
    id: "invent-refract",
    keywords: ["refraction", "refractive", "light", "snell", "lens", "wave"],
    title: "The Lifeguard's Path Dilemma",
    subject: "Physics (0625 & IIT)",
    historical_inventor: "Pierre de Fermat & Willebrord Snell",
    year: "1621",
    target_concept: "Snell's Law of Refraction",
    formal_formula: "n = \\frac{\\sin i}{\\sin r} = \\frac{v_1}{v_2}",
    mystery_story:
      "A lifeguard standing on the sandy beach spots a swimmer struggling in the sea at an angle. " +
      "She can run on sand at 6 m/s, but can only swim in water at 2 m/s. " +
      "Which path should she take to reach the swimmer in the least possible time?",
    case_data: [
      { label: "Path A (Straight line)", values: "Shortest geometric distance", note: "Spends too long swimming slowly!" },
      { label: "Path B (Optimal bent path)", values: "More sand, less water", note: "Minimizes total elapsed seconds!" },
    ],
    intuitive_failure_point:
      "Intuition says 'the shortest path between two points is a straight line'. But when speeds differ across two media, " +
      "the shortest distance is NOT the fastest time! Light faces this exact physical trade-off when moving from air into glass.",
    discovery_reveal:
      "Light always takes the path of least time (Fermat's Principle). Because light slows down in glass or water, " +
      "it bends towards the normal at the boundary such that $\\sin i / \\sin r$ remains constant!",
  },
];

export function InventingToLearn({ statement = "" }: { statement?: string }) {
  const lower = statement.toLowerCase();
  const matched = MYSTERY_CASES.filter((mc) => mc.keywords.some((kw) => lower.includes(kw)));

  const [studentHypothesis, setStudentHypothesis] = useState("");
  const [revealed, setRevealed] = useState(false);

  if (matched.length === 0) {
    return null;
  }

  const c = matched[0];

  return (
    <Card
      title="💡 First-Principles Discovery Scenario"
      subtitle="See the real-world dilemma that led to this concept"
      tone="purple"
    >
      <div className="space-y-4">
        <div className="p-4 rounded-2xl border border-purple-200 bg-gradient-to-r from-purple-50/70 via-white to-amber-50/70 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <span className="font-fun font-bold text-xs uppercase tracking-wider text-purple-700">
              {c.title} · {c.subject}
            </span>
            <Chip tone="brand">{c.target_concept}</Chip>
          </div>
          <p className="text-sm font-medium text-slate-800 leading-relaxed">
            {c.mystery_story}
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {c.case_data.map((cd, i) => (
            <div
              key={i}
              className="p-3 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-1"
            >
              <div className="font-fun font-bold text-xs text-purple-900">{cd.label}</div>
              <div className="font-mono text-sm font-bold text-slate-800">{cd.values}</div>
              <div className="text-[11px] text-slate-500 font-medium">{cd.note}</div>
            </div>
          ))}
        </div>

        <div className="p-3.5 rounded-2xl bg-amber-50 border border-slate-200 text-xs text-amber-950 space-y-1">
          <span className="font-fun font-bold flex items-center gap-1.5 text-amber-900">
            <span>⚠️</span> The Intuitive Trap
          </span>
          <p className="leading-relaxed">{c.intuitive_failure_point}</p>
        </div>

        {!revealed ? (
          <div className="space-y-2.5 pt-1">
            <label className="block text-xs font-fun font-bold text-slate-800">
              How would you design a rule or formula to resolve this?
            </label>
            <textarea
              value={studentHypothesis}
              onChange={(e) => setStudentHypothesis(e.target.value)}
              rows={2}
              className="w-full rounded-2xl border-2 border-purple-200 bg-white p-3 text-xs outline-none focus:border-purple-400 placeholder:text-slate-400"
              placeholder="Jot down your idea before revealing the mathematical breakthrough…"
            />
            <Button onClick={() => setRevealed(true)} className="w-full sm:w-auto">
              Reveal Historical Breakthrough 🔬
            </Button>
          </div>
        ) : (
          <div className="p-4 rounded-2xl bg-gradient-to-r from-emerald-50 to-teal-50 border-2 border-emerald-300 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xl">🎉</span>
                <span className="font-fun font-bold text-sm text-emerald-950">
                  {c.historical_inventor} ({c.year})
                </span>
              </div>
              <Chip tone="good">First Principles</Chip>
            </div>
            <p className="text-xs text-slate-700 leading-relaxed font-medium">
              {c.discovery_reveal}
            </p>
            <div className="p-3 rounded-xl bg-white border border-emerald-200 text-center">
              <div className="text-base font-bold text-emerald-900">
                <MathText text={`$$${c.formal_formula}$$`} />
              </div>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
