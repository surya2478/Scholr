"use client";

import { useState } from "react";
import { MathText } from "@/components/MathText";
import { Button, Card, Chip } from "@/components/ui";

type MysteryCase = {
  id: string;
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
    title: "The Mystery of the Identical Averages",
    subject: "Mathematics (0580 & IIT)",
    historical_inventor: "Karl Pearson",
    year: "1893",
    target_concept: "Standard Deviation & Spread",
    formal_formula: "\\sigma = \\sqrt{\\frac{\\sum (x - \\mu)^2}{N}}",
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
      "(40-70) + (55-70) + (70-70) + (85-70) + (100-70) = (-30) + (-15) + 0 + 15 + 30 = 0! " +
      "The positive and negative deviations completely cancel each other out!",
    discovery_reveal:
      "In 1893, Karl Pearson solved this exact trap with a flash of genius: square each distance from the mean " +
      "so negatives become positive ($(-30)^2 = 900$), find their average, then square root it back to the original units. " +
      "You just reinvented Standard Deviation!",
  },
  {
    id: "invent-refract",
    title: "The Lifeguard's Path Dilemma",
    subject: "Physics (0625 & IIT)",
    historical_inventor: "Pierre de Fermat & Willebrord Snell",
    year: "1621",
    target_concept: "Snell's Law of Refraction",
    formal_formula: "\\frac{\\sin \\theta_1}{\\sin \\theta_2} = \\frac{v_1}{v_2} = \\frac{n_2}{n_1}",
    mystery_story:
      "A lifeguard standing on the sandy beach spots a swimmer struggling in the sea at an angle. " +
      "She can run on sand at 6 m/s, but can only swim in water at 2 m/s. " +
      "Which path should she take to reach the swimmer in the least possible time?",
    case_data: [
      { label: "Path A (Straight line)", values: "Shortest geometric distance", note: "Spends a long time swimming slowly!" },
      { label: "Path B (Run straight to shore, then swim)", values: "Max running distance", note: "Geometric distance is too long!" },
      { label: "Path C (The Angle of Refraction)", values: "Optimal bent path", note: "Minimizes total elapsed seconds!" },
    ],
    intuitive_failure_point:
      "Intuition says 'the shortest path between two points is a straight line'. But when speeds differ across two media, " +
      "the shortest distance is NOT the fastest time! Light faces this exact physical trade-off when moving from air to glass.",
    discovery_reveal:
      "Light always takes the path of least time (Fermat's Principle). Because light moves slower in water or glass, " +
      "it 'bends' at the boundary. Snell discovered the exact invariant ratio that nature uses: the ratio of the sines of the angles " +
      "equals the ratio of wave velocities!",
  },
];

export function InventingToLearn() {
  const [activeCaseIndex, setActiveCaseIndex] = useState(0);
  const [studentHypothesis, setStudentHypothesis] = useState("");
  const [revealed, setRevealed] = useState(false);

  const c = MYSTERY_CASES[activeCaseIndex];

  return (
    <Card
      title="💡 Inventing-to-Learn (Mystery Scenarios)"
      subtitle="Stanford AAA Lab Framework: Invent the concept before being given the textbook formula"
      tone="purple"
    >
      <div className="space-y-4">
        {/* Case Switcher */}
        <div className="flex flex-wrap gap-2">
          {MYSTERY_CASES.map((item, idx) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                setActiveCaseIndex(idx);
                setStudentHypothesis("");
                setRevealed(false);
              }}
              className={`px-3.5 py-1.5 rounded-xl font-fun font-bold text-xs transition-all cursor-pointer ${
                activeCaseIndex === idx
                  ? "bg-purple-600 text-white shadow-xs"
                  : "bg-purple-50 text-purple-800 hover:bg-purple-100 border border-purple-200"
              }`}
            >
              {item.title}
            </button>
          ))}
        </div>

        {/* Story Box */}
        <div className="p-4 rounded-2xl border border-purple-200 bg-gradient-to-r from-purple-50/70 via-white to-amber-50/70 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <span className="font-fun font-bold text-xs uppercase tracking-wider text-purple-700">
              The Mystery Dilemma · {c.subject}
            </span>
            <Chip tone="brand">Target: {c.target_concept}</Chip>
          </div>
          <p className="text-sm font-medium text-slate-800 leading-relaxed">
            {c.mystery_story}
          </p>
        </div>

        {/* Contrasting Case Data */}
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

        {/* Challenge & Failure Point */}
        <div className="p-3.5 rounded-2xl bg-amber-50 border border-amber-200 text-xs text-amber-950 space-y-1">
          <span className="font-fun font-bold flex items-center gap-1.5 text-amber-900">
            <span>⚠️</span> The Intuitive Trap
          </span>
          <p className="leading-relaxed">{c.intuitive_failure_point}</p>
        </div>

        {/* Student Hypothesis Area */}
        {!revealed ? (
          <div className="space-y-2.5 pt-1">
            <label className="block text-xs font-fun font-bold text-slate-800">
              How would you invent a mathematical rule or formula to solve this?
            </label>
            <textarea
              value={studentHypothesis}
              onChange={(e) => setStudentHypothesis(e.target.value)}
              rows={2}
              className="w-full rounded-2xl border-2 border-purple-200 bg-white p-3 text-xs outline-none focus:border-purple-400 placeholder:text-slate-400"
              placeholder="Describe your invented rule or formula prototype..."
            />
            <Button
              onClick={() => setRevealed(true)}
              className="w-full sm:w-auto"
            >
              Test My Invention & Reveal Historical Breakthrough 🔬
            </Button>
          </div>
        ) : (
          /* Reveal Historical Discovery */
          <div className="p-4 rounded-2xl bg-gradient-to-r from-emerald-50 to-teal-50 border-2 border-emerald-300 space-y-3 animate-fadeIn">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-2xl">🎉</span>
                <span className="font-fun font-bold text-sm text-emerald-950">
                  {c.historical_inventor} ({c.year}) faced this exact dilemma!
                </span>
              </div>
              <Chip tone="good">Formula Unlocked</Chip>
            </div>

            <p className="text-xs text-slate-700 leading-relaxed font-medium">
              {c.discovery_reveal}
            </p>

            <div className="p-3 rounded-xl bg-white border border-emerald-200 text-center">
              <span className="text-[11px] font-fun font-bold text-slate-400 block uppercase tracking-wider mb-1">
                Official Curriculum Formula
              </span>
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
