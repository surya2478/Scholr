"use client";

import { useState } from "react";
import { Button, Card, Chip, Empty, ErrorNote } from "@/components/ui";
import type { CrucibleTopic, SociologistAvatar } from "@/lib/api";
import { useApi } from "@/lib/useApi";

export function DialecticalCrucible({ unitName }: { unitName?: string }) {
  const topics = useApi<CrucibleTopic[]>(
    `/curriculum/crucible${unitName ? `?syllabus_unit=${unitName}` : ""}`
  );
  const [activeTopicIndex, setActiveTopicIndex] = useState(0);
  const [activeAvatarIndex, setActiveAvatarIndex] = useState<number | null>(0);
  const [synthesisText, setSynthesisText] = useState("");
  const [verdictBand, setVerdictBand] = useState<string | null>(null);

  const topic = topics.data?.[activeTopicIndex];

  function evaluateEssaySynthesis() {
    if (!synthesisText.trim()) return;
    const lower = synthesisText.toLowerCase();
    let score = 0;
    // Check for theoretical perspective markers
    if (lower.includes("functionalist") || lower.includes("parsons") || lower.includes("meritocra")) score += 1;
    if (lower.includes("marxist") || lower.includes("bowles") || lower.includes("reproduction") || lower.includes("capital")) score += 1;
    if (lower.includes("feminist") || lower.includes("gender") || lower.includes("patriarch") || lower.includes("oakley")) score += 1;
    // Check for evaluative connective phrases
    if (lower.includes("however") || lower.includes("on the other hand") || lower.includes("in contrast") || lower.includes("nevertheless")) score += 1;
    if (lower.includes("to some extent") || lower.includes("in conclusion") || lower.includes("overall") || lower.includes("evaluat")) score += 1;

    if (score >= 4) {
      setVerdictBand("Level 4 (Top Band: 12-15 Marks) 🌟 Effective evaluation weighing multiple structural theories!");
    } else if (score >= 2) {
      setVerdictBand("Level 3 (Mid Band: 8-11 Marks) 👍 Solid explanation of theories, but strengthen your final 'To what extent' evaluation.");
    } else {
      setVerdictBand("Level 2 (Basic: 4-7 Marks) 💡 Mention more specific sociologists and empirical studies.");
    }
  }

  if (topics.data?.length === 0) {
    return null;
  }

  return (
    <Card
      title="⚖️ The Dialectical Crucible (AO3 Essay Synthesizer)"
      subtitle="Cambridge 0495 15-Mark Essay Evaluator (Hegelian Thesis ↔ Antithesis ↔ Synthesis)"
      tone="purple"
    >
      {topics.error ? <ErrorNote error={topics.error} /> : null}

      {topic ? (
        <div className="space-y-5">
          {/* Question Banner */}
          <div className="rounded-2xl border-2 border-purple-200 bg-gradient-to-r from-purple-50 via-white to-indigo-50 p-4 shadow-2xs space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <span className="font-fun font-bold text-xs uppercase tracking-wider text-purple-700">
                15-Mark Evaluative Essay Prompt ({topic.syllabus_unit} Unit)
              </span>
              <Chip tone="brand">AO3 Analysis & Evaluation</Chip>
            </div>
            <h3 className="text-base font-fun font-bold text-slate-900 leading-snug">
              &ldquo;{topic.essay_question}&rdquo;
            </h3>
            <div className="text-[11px] text-slate-500 font-medium pt-1">
              Official Rubric: {topic.ao3_level_4_descriptor}
            </div>
          </div>

          {/* Theoretical Roundtable: Avatars */}
          <div className="space-y-2">
            <div className="text-xs font-fun font-bold text-slate-700 uppercase tracking-wider">
              Step 1: The Roundtable Perspectives (Click an avatar to hear their thesis)
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {topic.avatars.map((av: SociologistAvatar, idx: number) => (
                <button
                  key={av.name}
                  type="button"
                  onClick={() => setActiveAvatarIndex(idx)}
                  className={`text-left p-3.5 rounded-2xl border-2 transition-all cursor-pointer ${
                    activeAvatarIndex === idx
                      ? "border-purple-500 bg-purple-50 shadow-sm scale-102"
                      : "border-slate-200 bg-white hover:border-purple-300"
                  }`}
                >
                  <div className="flex items-center justify-between text-xs font-fun font-bold mb-1">
                    <span className="text-slate-900">{av.name}</span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] ${
                      av.perspective === "Functionalist" ? "bg-amber-100 text-amber-900" :
                      av.perspective === "Marxist" ? "bg-rose-100 text-rose-900" : "bg-purple-100 text-purple-900"
                    }`}>
                      {av.perspective}
                    </span>
                  </div>
                  <div className="text-[11px] font-semibold text-purple-900 mb-1">
                    {av.key_concept}
                  </div>
                  <p className="text-xs text-slate-600 line-clamp-3 leading-relaxed">
                    &ldquo;{av.core_thesis}&rdquo;
                  </p>
                </button>
              ))}
            </div>
          </div>

          {/* Active Avatar Deep-Dive */}
          {activeAvatarIndex !== null && topic.avatars[activeAvatarIndex] && (
            <div className="p-4 rounded-2xl bg-[#FFFDF9] border border-purple-200 text-xs text-slate-800 space-y-2">
              <div className="font-fun font-bold text-purple-900 flex items-center gap-1.5">
                <span>📖</span>
                <span>{topic.avatars[activeAvatarIndex].name}&apos;s Core Sociological Argument</span>
              </div>
              <p className="leading-relaxed text-slate-700">
                {topic.avatars[activeAvatarIndex].core_thesis}
              </p>
              <div className="pt-2 border-t border-purple-100 flex items-center gap-2 text-[11px] font-medium text-slate-500">
                <span className="font-bold text-purple-800">Key Evidence / Study:</span>
                <span>{topic.avatars[activeAvatarIndex].empirical_evidence}</span>
              </div>
            </div>
          )}

          {/* Step 2: Synthesis Crucible Arena */}
          <div className="space-y-3 pt-2 border-t border-purple-100">
            <div className="text-xs font-fun font-bold text-slate-700 uppercase tracking-wider">
              Step 2: Act as The Judge (Synthesize a Level 4 Balanced Conclusion)
            </div>

            <div className="bg-purple-50/60 p-3 rounded-xl border border-purple-200 text-xs text-purple-950 space-y-1">
              <span className="font-fun font-bold block">Examiner Guidance for 15 Marks:</span>
              <ul className="list-disc ml-4 space-y-0.5 text-slate-700 text-[11px]">
                {topic.synthesis_guidelines.map((g: string, i: number) => (
                  <li key={i}>{g}</li>
                ))}
              </ul>
            </div>

            <textarea
              value={synthesisText}
              onChange={(e) => setSynthesisText(e.target.value)}
              rows={4}
              className="w-full rounded-2xl border-2 border-purple-200 bg-white p-3.5 text-xs font-normal outline-none focus:border-purple-400 placeholder:text-slate-400"
              placeholder="Draft your AO3 conclusion here... (e.g. While Parsons and functionalists argue that schools are meritocratic, Bowles & Gintis demonstrate social reproduction. To a large extent...)"
            />

            <Button
              disabled={!synthesisText.trim()}
              onClick={evaluateEssaySynthesis}
              className="w-full sm:w-auto"
            >
              Assess My AO3 Level 4 Verdict ⚖️
            </Button>

            {verdictBand && (
              <div className="p-4 rounded-2xl bg-gradient-to-r from-purple-50 to-indigo-50 border-2 border-purple-300 text-xs text-purple-950 font-medium space-y-1 animate-fadeIn">
                <div className="font-fun font-bold text-sm text-purple-900">
                  Cambridge Examiner Assessment:
                </div>
                <p className="leading-relaxed">{verdictBand}</p>
              </div>
            )}
          </div>
        </div>
      ) : (
        <Empty>No debate prompts loaded for this unit yet.</Empty>
      )}
    </Card>
  );
}
