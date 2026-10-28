"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { Attempt, Evaluation, ItemCard, Lesson, Question } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { AnswerBox } from "../AnswerBox";
import { MathText } from "../MathText";
import { ErrorNote } from "../ui";

export type DifficultyTier = "easy" | "medium" | "hard";

export type UnifiedQuestionItem = {
  uid: string;
  kind: "bank" | "worked_example" | "exam_answer";
  difficulty: DifficultyTier;
  category: string;
  marks: number;
  label: string;
  tierLabel: string;
  commandWord: string | null;
  context: string | null;
  stem: string;
  bankItem?: ItemCard;
  modelPoints?: string[];
  workedSteps?: string[];
  finalAnswer?: string;
  unit?: string | null;
  strategy?: string;
  takeaway?: string;
  sources?: { title: string; page: number | null }[];
};

// Two per-browser keys, kept under their original names so nothing she has saved is dropped.
// They are not evidence: self-marking belongs in `learning_event` (docs/GO-LIVE-ENGAGEMENT.md B5).
const SAVED_STORAGE_KEY = "scholr:sme-saved-questions:v1";
const SELF_SCORE_STORAGE_KEY = "scholr:sme-self-scores:v1";

function inferCommandWord(stem: string, fallback: string | null): string | null {
  if (fallback) return fallback;
  const cleaned = stem.trim();
  const match = cleaned.match(
    /^(Calculate|Find|Solve|Simplify|Factorise|Factorize|Expand|Work out|Show that|Prove|State|Identify|Define|Describe|Explain|Evaluate|To what extent|Compare|Discuss|Give|Name|Write down)\b/i
  );
  return match ? match[1] : null;
}

function classifyBankDifficulty(item: ItemCard, subjectCode: string): DifficultyTier {
  if (subjectCode === "igcse-sociology") {
    if (item.marks <= 4) return "easy";
    if (item.marks <= 8) return "medium";
    return "hard";
  }
  if (subjectCode === "igcse-maths") {
    if (item.marks <= 2 && (item.difficulty ?? 2) <= 2) return "easy";
    if (item.marks <= 4 && (item.difficulty ?? 3) <= 3) return "medium";
    if (item.marks >= 5 || (item.difficulty ?? 0) >= 4) return "hard";
    return item.marks <= 2 ? "easy" : "medium";
  }
  if (item.difficulty !== null && item.difficulty !== undefined) {
    if (item.difficulty <= 2) return "easy";
    if (item.difficulty === 3) return "medium";
    return "hard";
  }
  if (item.marks <= 2) return "easy";
  if (item.marks <= 4) return "medium";
  return "hard";
}

function classifyBankCategory(item: ItemCard, subjectCode: string): string {
  if (subjectCode === "igcse-sociology") {
    if (item.marks <= 4) return "short";
    if (item.marks <= 8) return "structured";
    return "essay";
  }
  if (subjectCode === "igcse-maths") {
    const ref = item.source_ref ?? "";
    if (ref.includes("/21/") || ref.includes("/22/") || ref.includes("/23/") || item.marks <= 2) {
      return "paper2";
    }
    return "paper4";
  }
  return item.marks <= 2 ? "short" : "extended";
}

function buildCoachingHelp(item: UnifiedQuestionItem, subjectCode: string): {
  title: string;
  bullets: string[];
  rubricTip: string;
} {
  const cw = (item.commandWord ?? "").toLowerCase();

  if (subjectCode === "igcse-sociology") {
    if (item.marks <= 2 || cw === "identify" || cw === "define" || cw === "state" || cw === "give") {
      return {
        title: "Cambridge 0495 Short-Answer Examiner Guide (1–2 marks)",
        bullets: [
          "Write a direct, concise sociological point or definition — no long introduction needed.",
          "For 2-mark 'Define' or 'Identify two' questions: give 1 clear point + 1 brief development or example.",
          "Use accurate sociological terminology from this topic's glossary.",
        ],
        rubricTip: "Award 1 mark for a partial definition/point, 2 marks for a full sociological definition or two distinct points.",
      };
    }
    if (item.marks <= 4 || cw === "describe") {
      return {
        title: "Cambridge 0495 'Describe' Formula (4 marks = 2 × Point + Development)",
        bullets: [
          "Identify TWO distinct sociological points relevant to the question.",
          "For each point, add a second sentence of development (how/why it happens, a sociological concept, or an example).",
          "Keep the two points clearly separated so the examiner can award 2 + 2 marks immediately.",
        ],
        rubricTip: "1 mark for each valid point identified (up to 2) + 1 mark for each clear sociological development (up to 2).",
      };
    }
    if (item.marks <= 8 || cw === "explain") {
      return {
        title: `Cambridge 0495 Structured 'Explain' Guide (${item.marks} marks)`,
        bullets: [
          item.marks === 6
            ? "Write 3 developed paragraphs (or 2 deeply developed sociological arguments) using PEEL: Point → Explanation → Evidence/Concept → Link."
            : "Write 4 developed PEEL paragraphs (4 × 2 marks = 8 marks).",
          "Include named sociological concepts, perspectives (e.g., Functionalism, Marxism, Feminism), or studies where relevant.",
          "Always end each paragraph by linking back to the exact wording of the question.",
        ],
        rubricTip: `Up to ${item.marks} marks: 1 mark per valid sociological point + 1 mark for explaining how/why it answers the question using sociological terms.`,
      };
    }
    return {
      title: `Cambridge 0495 Extended Evaluation Essay Guide (${item.marks} marks)`,
      bullets: [
        "Build a balanced two-sided debate: 3 developed arguments FOR the statement + 3 developed arguments AGAINST.",
        "Anchor both sides in sociological theories (Functionalist, Marxist, Feminist, Interactionist, Postmodernist) and empirical evidence.",
        "Finish with a Weighing-Up Conclusion that makes a reasoned sociological judgement ('Overall, to a large extent because...') rather than just repeating points.",
      ],
      rubricTip: "Band 4 (Top Band): Balanced arguments For & Against, sustained sociological concepts/theorists, and a clear evaluative judgement.",
    };
  }

  if (subjectCode === "igcse-maths") {
    return {
      title: `Cambridge 0580 Extended Maths Coaching (${item.marks} mark${item.marks === 1 ? "" : "s"})`,
      bullets: [
        item.strategy
          ? `Game Plan: ${item.strategy}`
          : "Step 1: Write down the governing formula or algebraic equation before substituting numbers.",
        item.marks >= 3
          ? "Show every intermediate algebraic step clearly — Method marks (M1/M2) are awarded even if your final arithmetic slips."
          : "Check whether the question asks for an exact value (fraction/surd/in terms of π) or 3 significant figures.",
        item.takeaway
          ? `Examiner Trap to Avoid: ${item.takeaway}`
          : "Verify units, signs (especially negative brackets), and rounding accuracy before submitting.",
      ],
      rubricTip:
        item.marks === 1
          ? "B1 mark: Awarded for the correct final value."
          : `M${Math.max(1, item.marks - 1)} method marks for valid algebraic/geometric working + A1 accuracy mark for the exact final answer.`,
    };
  }

  return {
    title: `Examiner Method Guide (${item.marks} mark${item.marks === 1 ? "" : "s"})`,
    bullets: [
      item.strategy || "Read the command word carefully and match the number of distinct points to the mark allocation.",
      "Use precise syllabus terminology and show every step of your reasoning.",
      item.takeaway || "Double-check units and significant figures on numerical answers.",
    ],
    rubricTip: `1 mark per distinct mark-scheme point or method step up to ${item.marks} marks.`,
  };
}

function BankQuestionSolver({
  item,
  askHref,
  onScored,
}: {
  item: ItemCard;
  askHref: (q: string) => string;
  onScored: (awarded: number, available: number) => void;
}) {
  const question = useApi<Question>(`/questions/${item.id}`);

  if (question.error) {
    return (
      <div className="mt-3">
        <ErrorNote error={question.error} />
      </div>
    );
  }

  if (question.loading || !question.data) {
    return (
      <div className="mt-4 flex items-center gap-2.5 rounded-2xl border border-teal-200 bg-teal-50/50 p-4 text-xs font-semibold text-teal-800">
        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-teal-600 border-t-transparent" />
        <span>Loading interactive Cambridge marking workspace…</span>
      </div>
    );
  }

  return (
    <div className="mt-4 rounded-2xl border-2 border-teal-200/80 bg-slate-50/60 p-4">
      <AnswerBox
        question={question.data}
        onAnswered={(_attempt: Attempt, evaluation: Evaluation | null) => {
          if (evaluation) {
            onScored(evaluation.marks_awarded, question.data?.marks ?? item.marks);
          }
        }}
      />
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-200/80 pt-3">
        <Link
          href={askHref(question.data.stem)}
          className="text-xs font-fun font-bold text-teal-700 hover:underline"
        >
          🦉 Ask the Scholr Tutor for a step-by-step hint on this question →
        </Link>
      </div>
    </div>
  );
}

export function TopicQuestions({
  topicName,
  topicCode,
  subjectName,
  subjectCode,
  syllabusCode,
  checkYourself,
  examQuestions,
  lesson,
  askHref,
  onQuestionAnswered,
}: {
  topicName: string;
  topicCode: string;
  subjectName: string;
  subjectCode: string;
  syllabusCode: string | null;
  checkYourself: ItemCard[];
  examQuestions: ItemCard[];
  lesson: Lesson | null;
  askHref: (q: string) => string;
  onQuestionAnswered?: () => void;
}) {
  // Combine and deduplicate all questions for this topic
  const allItems = useMemo<UnifiedQuestionItem[]>(() => {
    const out: UnifiedQuestionItem[] = [];
    const seenBankIds = new Set<string>();

    for (const card of [...checkYourself, ...examQuestions]) {
      if (seenBankIds.has(card.id)) continue;
      seenBankIds.add(card.id);
      const diff = classifyBankDifficulty(card, subjectCode);
      const cat = classifyBankCategory(card, subjectCode);
      const stem = card.stem ?? "Open question to view full stem.";
      out.push({
        uid: `bank-${card.id}`,
        kind: "bank",
        difficulty: diff,
        category: cat,
        marks: card.marks,
        label: card.label,
        tierLabel:
          subjectCode === "igcse-maths"
            ? card.marks >= 3
              ? "Extended tier · Paper 4 style"
              : "Core & Extended · Paper 2 style"
            : subjectCode === "igcse-sociology"
            ? card.marks >= 10
              ? "Paper 1/2 · Extended Evaluation"
              : card.marks >= 6
              ? "Paper 1/2 · Structured Explain"
              : "Paper 1/2 · Short Answer"
            : card.label,
        commandWord: inferCommandWord(stem, card.command_word),
        context: card.context ?? null,
        stem,
        bankItem: card,
      });
    }

    // Also include worked examples (especially valuable in Mathematics where some topics have fewer bank items)
    if (lesson?.worked_examples) {
      lesson.worked_examples.forEach((ex, idx) => {
        const diff: DifficultyTier =
          ex.level === "basic" ? "easy" : ex.level === "exam" ? "hard" : "medium";
        const marks = diff === "easy" ? 2 : diff === "medium" ? 3 : 5;
        out.push({
          uid: `worked-${idx}`,
          kind: "worked_example",
          difficulty: diff,
          category: subjectCode === "igcse-maths" ? "worked" : "model",
          marks,
          label: `Guided Practice Q${idx + 1}`,
          tierLabel:
            ex.checked === "sympy"
              ? `SymPy-Verified ${diff.charAt(0).toUpperCase() + diff.slice(1)} Drill`
              : `Guided ${diff.charAt(0).toUpperCase() + diff.slice(1)} Example`,
          commandWord: inferCommandWord(ex.problem, subjectCode === "igcse-maths" ? "Calculate" : "Explain"),
          context: null,
          stem: ex.problem,
          workedSteps: ex.steps,
          finalAnswer: ex.final_answer,
          unit: ex.unit,
          strategy: ex.strategy,
          takeaway: ex.coaching_takeaway,
          sources: ex.sources,
        });
      });
    }

    // Also include exam_answers from the lesson as model answer drills
    if (lesson?.exam_answers) {
      lesson.exam_answers.forEach((ea, idx) => {
        const marks = Math.max(2, ea.points.length);
        const diff: DifficultyTier = marks <= 2 ? "easy" : marks <= 4 ? "medium" : "hard";
        out.push({
          uid: `model-${idx}`,
          kind: "exam_answer",
          difficulty: diff,
          category: subjectCode === "igcse-maths" ? "worked" : "model",
          marks,
          label: `Model Exam Question ${idx + 1}`,
          tierLabel: `Cambridge ${marks}-Mark Model Drill`,
          commandWord: inferCommandWord(ea.question, null),
          context: null,
          stem: ea.question,
          modelPoints: ea.points,
          sources: ea.sources,
        });
      });
    }

    return out;
  }, [checkYourself, examQuestions, lesson, subjectCode]);

  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [difficultyTab, setDifficultyTab] = useState<DifficultyTier>("easy");
  const [savedOnly, setSavedOnly] = useState(false);
  const [activeNumber, setActiveNumber] = useState<number>(1);
  const [savedIds, setSavedIds] = useState<string[]>([]);
  const [scores, setScores] = useState<Record<string, { awarded: number; available: number }>>({});
  const [openMarkId, setOpenMarkId] = useState<string | null>(null);
  const [openHelpId, setOpenHelpId] = useState<string | null>(null);
  const [openAnswerId, setOpenAnswerId] = useState<string | null>(null);
  const [fullscreenItem, setFullscreenItem] = useState<{ item: UnifiedQuestionItem; index: number } | null>(null);
  const [helpfulVote, setHelpfulVote] = useState<Record<string, "yes" | "no">>({});
  const [scratchInputs, setScratchInputs] = useState<Record<string, string>>({});

  // Load saved bookmarks and self-scores from localStorage + initial bank scores
  useEffect(() => {
    try {
      const rawSaved = window.localStorage.getItem(SAVED_STORAGE_KEY);
      if (rawSaved) setSavedIds(JSON.parse(rawSaved));
      const rawScores = window.localStorage.getItem(SELF_SCORE_STORAGE_KEY);
      const parsedScores: Record<string, { awarded: number; available: number }> = rawScores
        ? JSON.parse(rawScores)
        : {};
      // Merge server-side last_marks from bank items
      for (const item of allItems) {
        if (
          item.bankItem &&
          item.bankItem.last_marks !== null &&
          item.bankItem.last_marks !== undefined
        ) {
          parsedScores[item.uid] = {
            awarded: item.bankItem.last_marks,
            available: item.marks,
          };
        }
      }
      setScores(parsedScores);
    } catch {
      // ignore storage errors
    }
  }, [allItems]);

  // Ensure initial difficulty tab has questions if "easy" is empty
  useEffect(() => {
    const easyCount = allItems.filter((i) => i.difficulty === "easy").length;
    const medCount = allItems.filter((i) => i.difficulty === "medium").length;
    const hardCount = allItems.filter((i) => i.difficulty === "hard").length;
    if (easyCount === 0 && medCount > 0) {
      setDifficultyTab("medium");
    } else if (easyCount === 0 && medCount === 0 && hardCount > 0) {
      setDifficultyTab("hard");
    }
  }, [allItems]);

  // Sync with the URL hash (#easy-2, #medium-1, #hard-3) so a question can be linked to directly.
  useEffect(() => {
    function syncFromHash() {
      const hash = window.location.hash.replace(/^#/, "").toLowerCase();
      const match = hash.match(/^(easy|medium|hard)-(\d+)$/);
      if (match) {
        const tier = match[1] as DifficultyTier;
        const num = parseInt(match[2], 10);
        setDifficultyTab(tier);
        if (num >= 1) {
          setActiveNumber(num);
          window.setTimeout(() => {
            const el = document.getElementById(`${tier}-${num}`);
            if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
          }, 80);
        }
      }
    }
    syncFromHash();
    window.addEventListener("hashchange", syncFromHash);
    return () => window.removeEventListener("hashchange", syncFromHash);
  }, []);

  function toggleSaved(uid: string) {
    setSavedIds((prev) => {
      const next = prev.includes(uid) ? prev.filter((x) => x !== uid) : [...prev, uid];
      try {
        window.localStorage.setItem(SAVED_STORAGE_KEY, JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });
  }

  function recordScore(uid: string, awarded: number, available: number) {
    setScores((prev) => {
      const next = { ...prev, [uid]: { awarded, available } };
      try {
        window.localStorage.setItem(SELF_SCORE_STORAGE_KEY, JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });
    onQuestionAnswered?.();
  }

  // Category tabs tailored for Sociology (0495) first, then Mathematics (0580)
  const categoryTabs = useMemo(() => {
    if (subjectCode === "igcse-sociology") {
      return [
        { key: "all", label: "All Topic Questions" },
        { key: "short", label: "Short Answer (1–4m)" },
        { key: "structured", label: "Structured Explain (6–8m)" },
        { key: "essay", label: "Evaluation Essays (10–15m)" },
        { key: "model", label: "Model Exam Drills" },
      ];
    }
    if (subjectCode === "igcse-maths") {
      return [
        { key: "all", label: "All Topic Questions" },
        { key: "paper2", label: "Paper 2 Short (1–2m)" },
        { key: "paper4", label: "Paper 4 Extended (3+m)" },
        { key: "worked", label: "SymPy Practice Drills" },
      ];
    }
    return [
      { key: "all", label: "All Topic Questions" },
      { key: "short", label: "Short Response (1–2m)" },
      { key: "extended", label: "Extended Response (3+m)" },
      { key: "model", label: "Model Drills" },
    ];
  }, [subjectCode]);

  const categoryFiltered = useMemo(() => {
    return allItems.filter((item) => {
      if (savedOnly && !savedIds.includes(item.uid)) return false;
      if (categoryFilter === "all") return true;
      return item.category === categoryFilter;
    });
  }, [allItems, categoryFilter, savedOnly, savedIds]);

  const countsByDifficulty = useMemo(() => {
    return {
      easy: categoryFiltered.filter((i) => i.difficulty === "easy").length,
      medium: categoryFiltered.filter((i) => i.difficulty === "medium").length,
      hard: categoryFiltered.filter((i) => i.difficulty === "hard").length,
    };
  }, [categoryFiltered]);

  const visibleItems = useMemo(() => {
    const inTier = categoryFiltered.filter((i) => i.difficulty === difficultyTab);
    return inTier.length > 0 ? inTier : categoryFiltered;
  }, [categoryFiltered, difficultyTab]);

  const totalMarks = useMemo(
    () => allItems.reduce((sum, item) => sum + item.marks, 0),
    [allItems]
  );
  const estMinutes = Math.max(10, Math.round(totalMarks * 1.2));
  const estDisplay =
    estMinutes >= 60
      ? `${(estMinutes / 60).toFixed(1).replace(/\.0$/, "")} hours`
      : `${estMinutes} mins`;

  const totalAwarded = useMemo(
    () => Object.values(scores).reduce((acc, s) => acc + s.awarded, 0),
    [scores]
  );

  function jumpToQuestion(indexOneBased: number) {
    setActiveNumber(indexOneBased);
    const anchor = `${difficultyTab}-${indexOneBased}`;
    window.history.replaceState(null, "", `#${anchor}`);
    const el = document.getElementById(anchor);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  function renderQuestionCard(item: UnifiedQuestionItem, indexZero: number, inModal = false) {
    const qNum = indexZero + 1;
    const anchorId = `${difficultyTab}-${qNum}`;
    const isSaved = savedIds.includes(item.uid);
    const score = scores[item.uid];
    const isMarkOpen = openMarkId === item.uid;
    const isHelpOpen = openHelpId === item.uid;
    const isAnswerOpen = openAnswerId === item.uid;
    const coaching = buildCoachingHelp(item, subjectCode);
    const vote = helpfulVote[item.uid];

    return (
      <article
        key={item.uid}
        id={inModal ? undefined : anchorId}
        onMouseEnter={() => setActiveNumber(qNum)}
        className={`scroll-mt-36 overflow-hidden rounded-2xl border-2 transition-all bg-white shadow-2xs ${
          activeNumber === qNum && !inModal
            ? "border-teal-500/80 ring-2 ring-teal-500/10"
            : "border-slate-200/90 hover:border-slate-300"
        }`}
      >
        {/* Question bar */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-50/90 px-4 py-3">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-900 text-xs font-fun font-bold text-white">
              {qNum}
            </span>
            <span className="rounded-md bg-teal-50 border border-teal-200 px-2.5 py-0.5 text-[11px] font-bold text-teal-900">
              {item.tierLabel}
            </span>
            {item.commandWord && (
              <span className="rounded-md bg-indigo-50 border border-indigo-200 px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider text-indigo-800">
                {item.commandWord}
              </span>
            )}
            <span className="text-xs font-medium text-slate-500">{item.label}</span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-fun font-bold text-slate-800">
              {item.marks} mark{item.marks === 1 ? "" : "s"}
            </span>
            {!inModal && (
              <button
                type="button"
                onClick={() => setFullscreenItem({ item, index: indexZero })}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-100 hover:text-slate-900 cursor-pointer transition"
                title="View question in full screen"
              >
                <span>⛶</span>
                <span className="hidden sm:inline">Full screen</span>
              </button>
            )}
            <button
              type="button"
              onClick={() => toggleSaved(item.uid)}
              className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1 text-xs font-semibold cursor-pointer transition ${
                isSaved
                  ? "border-amber-300 bg-amber-50 text-amber-900"
                  : "border-slate-200 bg-white text-slate-600 hover:bg-slate-100"
              }`}
            >
              <span>{isSaved ? "🔖" : "📑"}</span>
              <span>{isSaved ? "Saved" : "Save"}</span>
            </button>
          </div>
        </div>

        {/* Question Context & Stem Body */}
        <div className="p-5 md:p-6 space-y-4">
          {item.context && (
            <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3.5 text-xs md:text-sm text-slate-700 leading-relaxed">
              <div className="mb-1 text-[10px] font-fun font-bold uppercase tracking-wider text-slate-400">
                Source Stimulus / Context
              </div>
              <MathText text={item.context} />
            </div>
          )}

          <div className="flex items-start justify-between gap-4">
            <div className="text-base md:text-[17px] font-medium text-slate-900 leading-relaxed flex-1">
              <MathText text={item.stem} />
            </div>
            <span className="shrink-0 font-mono text-xs font-bold text-slate-400">
              [{item.marks}]
            </span>
          </div>

          {/* Dotted answer-line preview for Maths / short questions when the solver is closed */}
          {!isMarkOpen && subjectCode === "igcse-maths" && (
            <div className="pt-2 flex items-center justify-end gap-2 text-xs text-slate-400 font-mono">
              <span>{item.unit ? `Answer = ........................................ ${item.unit}` : "...................................................."}</span>
            </div>
          )}

          {/* Interactive Mark My Answer Drawer */}
          {isMarkOpen && (
            <div className="pt-2">
              {item.kind === "bank" && item.bankItem ? (
                <BankQuestionSolver
                  item={item.bankItem}
                  askHref={askHref}
                  onScored={(awarded, available) => recordScore(item.uid, awarded, available)}
                />
              ) : (
                <div className="rounded-2xl border-2 border-teal-200 bg-teal-50/30 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-fun font-bold uppercase tracking-wider text-teal-900">
                      ✍️ Write your working & answer before revealing the mark scheme
                    </span>
                    <span className="text-xs font-semibold text-teal-700">
                      {item.marks} marks available
                    </span>
                  </div>
                  <textarea
                    rows={3}
                    value={scratchInputs[item.uid] ?? ""}
                    onChange={(e) =>
                      setScratchInputs((prev) => ({ ...prev, [item.uid]: e.target.value }))
                    }
                    placeholder={
                      subjectCode === "igcse-maths"
                        ? "Write your formula, substitution steps, and final numerical answer here..."
                        : "Write your key sociological points, concepts, and explanation here..."
                    }
                    className="w-full rounded-xl border border-teal-200 bg-white p-3 text-sm text-slate-800 focus:border-teal-500 focus:outline-none"
                  />
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-bold text-slate-700">Self-mark against scheme:</span>
                      <button
                        type="button"
                        onClick={() => {
                          recordScore(item.uid, item.marks, item.marks);
                          setOpenAnswerId(item.uid);
                        }}
                        className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-fun font-bold text-white hover:bg-emerald-700 cursor-pointer"
                      >
                        ✓ Full Marks ({item.marks}/{item.marks})
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          recordScore(item.uid, Math.max(1, Math.floor(item.marks / 2)), item.marks);
                          setOpenAnswerId(item.uid);
                        }}
                        className="rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-fun font-bold text-white hover:bg-amber-600 cursor-pointer"
                      >
                        ~ Partial ({Math.max(1, Math.floor(item.marks / 2))}/{item.marks})
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          recordScore(item.uid, 0, item.marks);
                          setOpenAnswerId(item.uid);
                        }}
                        className="rounded-lg bg-rose-500 px-3 py-1.5 text-xs font-fun font-bold text-white hover:bg-rose-600 cursor-pointer"
                      >
                        ✗ Need Review (0/{item.marks})
                      </button>
                    </div>
                    <Link
                      href={askHref(item.stem)}
                      className="text-xs font-fun font-bold text-teal-700 hover:underline"
                    >
                      🦉 Ask Tutor to check my working →
                    </Link>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* "Question help" drawer */}
          {isHelpOpen && (
            <div className="rounded-2xl border-2 border-indigo-200 bg-indigo-50/50 p-4 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-base">💡</span>
                  <h4 className="text-xs font-fun font-bold uppercase tracking-wider text-indigo-950">
                    {coaching.title}
                  </h4>
                </div>
                <Link
                  href={askHref(item.stem)}
                  className="rounded-lg bg-indigo-600 px-3 py-1 text-xs font-fun font-bold text-white hover:bg-indigo-700"
                >
                  🦉 Open Interactive Tutor on Q{qNum}
                </Link>
              </div>
              <ul className="space-y-1.5 pl-4 list-disc text-xs md:text-sm text-indigo-950">
                {coaching.bullets.map((b, i) => (
                  <li key={i} className="leading-relaxed">
                    <MathText text={b} />
                  </li>
                ))}
              </ul>
              <div className="rounded-xl border border-indigo-200/80 bg-white/90 px-3 py-2 text-xs text-indigo-900">
                <span className="font-bold">How marks are awarded: </span>
                <MathText text={coaching.rubricTip} />
              </div>
            </div>
          )}

          {/* "View answer" drawer */}
          {isAnswerOpen && (
            <div className="rounded-2xl border-2 border-emerald-200 bg-emerald-50/40 p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-emerald-200/70 pb-2">
                <div className="flex items-center gap-2">
                  <span className=" rounded-md bg-emerald-600 px-2 py-0.5 text-[10px] font-fun font-bold uppercase tracking-wider text-white">
                    Mark Scheme & Model Solution
                  </span>
                  <span className="text-xs font-bold text-emerald-950">
                    {item.marks} mark{item.marks === 1 ? "" : "s"}
                  </span>
                </div>
                {item.sources && item.sources.length > 0 && (
                  <span className="text-[11px] font-medium text-emerald-700">
                    Source: {item.sources.map((s) => (s.page ? `${s.title} p.${s.page}` : s.title)).join(", ")}
                  </span>
                )}
              </div>

              {item.kind === "worked_example" && item.workedSteps && (
                <div className="space-y-2">
                  <ol className="space-y-2 text-sm text-slate-800">
                    {item.workedSteps.map((step, sIdx) => (
                      <li
                        key={sIdx}
                        className="flex items-start justify-between gap-3 rounded-xl bg-white p-3 border border-emerald-100"
                      >
                        <div className="flex items-start gap-2.5">
                          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-[11px] font-bold text-emerald-900">
                            {sIdx + 1}
                          </span>
                          <div className="leading-relaxed">
                            <MathText text={step} />
                          </div>
                        </div>
                        <span className="shrink-0 rounded bg-emerald-100 px-1.5 py-0.5 font-mono text-[11px] font-bold text-emerald-800">
                          [M1]
                        </span>
                      </li>
                    ))}
                  </ol>
                  {item.finalAnswer && (
                    <div className="flex items-center justify-between rounded-xl border-2 border-emerald-300 bg-white px-4 py-2.5 text-sm font-bold text-emerald-950">
                      <div>
                        Final Answer: <MathText text={item.finalAnswer} />
                        {item.unit ? ` ${item.unit}` : ""}
                      </div>
                      <span className="rounded bg-emerald-600 px-2 py-0.5 font-mono text-xs text-white">
                        [A1]
                      </span>
                    </div>
                  )}
                </div>
              )}

              {item.kind === "exam_answer" && item.modelPoints && (
                <ul className="space-y-2 text-sm text-slate-800">
                  {item.modelPoints.map((pt, pIdx) => (
                    <li
                      key={pIdx}
                      className="flex items-start justify-between gap-3 rounded-xl bg-white p-3 border border-emerald-100"
                    >
                      <div className="flex items-start gap-2">
                        <span className="text-emerald-600 font-bold">✓</span>
                        <div className="leading-relaxed">
                          <MathText text={pt} />
                        </div>
                      </div>
                      <span className="shrink-0 rounded bg-emerald-100 px-1.5 py-0.5 font-mono text-[11px] font-bold text-emerald-800">
                        [1 mark]
                      </span>
                    </li>
                  ))}
                </ul>
              )}

              {item.kind === "bank" && (
                <div className="space-y-2.5 text-xs md:text-sm text-slate-800">
                  <div className="rounded-xl bg-white p-3.5 border border-emerald-200 space-y-2">
                    <div className="font-bold text-emerald-950">
                      Official Cambridge Mark Scheme Structure ({item.marks} marks):
                    </div>
                    <p className="text-slate-700 leading-relaxed">
                      <MathText text={coaching.rubricTip} />
                    </p>
                    <ul className="space-y-1 pl-4 list-disc text-slate-700">
                      {coaching.bullets.map((b, idx) => (
                        <li key={idx}>
                          <MathText text={b} />
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-emerald-100/70 px-3.5 py-2.5 text-xs font-medium text-emerald-950">
                    <span>
                      Click <strong>Mark my answer</strong> to submit your attempt — Scholr checks your working against the verified Cambridge mark scheme and reveals full point-by-point feedback!
                    </span>
                    {!isMarkOpen && (
                      <button
                        type="button"
                        onClick={() => setOpenMarkId(item.uid)}
                        className="rounded-lg bg-emerald-700 px-3 py-1 font-fun font-bold text-white hover:bg-emerald-800 cursor-pointer"
                      >
                        Open Marker ✍️
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Action bar: "How did you do?" + [Mark my answer] [Question help] [View answer] */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 bg-slate-50/70 px-4 py-3">
          <div className="flex items-center gap-2.5">
            <span className="text-xs font-fun font-bold text-slate-700">How did you do?</span>
            {score ? (
              <span
                className={`rounded-full px-3 py-1 text-xs font-fun font-bold ${
                  score.awarded >= score.available
                    ? "bg-emerald-100 text-emerald-900 border border-emerald-300"
                    : score.awarded > 0
                    ? "bg-amber-100 text-amber-900 border border-amber-300"
                    : "bg-rose-100 text-rose-900 border border-rose-300"
                }`}
              >
                {score.awarded} / {score.available} marks {score.awarded >= score.available ? "✓" : ""}
              </span>
            ) : (
              <span className="rounded-full border border-slate-300 bg-white px-3 py-0.5 text-xs font-semibold text-slate-500">
                ? / {item.marks} marks
              </span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setOpenMarkId(isMarkOpen ? null : item.uid)}
              className={`rounded-xl px-4 py-2 text-xs font-fun font-bold transition cursor-pointer ${
                isMarkOpen
                  ? "bg-slate-900 text-white"
                  : "bg-teal-600 text-white hover:bg-teal-700 shadow-2xs"
              }`}
            >
              ✨ {isMarkOpen ? "Hide marker" : "Mark my answer"}
            </button>

            <button
              type="button"
              onClick={() => setOpenHelpId(isHelpOpen ? null : item.uid)}
              className={`rounded-xl border px-3.5 py-2 text-xs font-fun font-bold transition cursor-pointer ${
                isHelpOpen
                  ? "border-indigo-300 bg-indigo-100 text-indigo-950"
                  : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
              }`}
            >
              💡 Question help
            </button>

            <button
              type="button"
              onClick={() => setOpenAnswerId(isAnswerOpen ? null : item.uid)}
              className={`rounded-xl border px-3.5 py-2 text-xs font-fun font-bold transition cursor-pointer ${
                isAnswerOpen
                  ? "border-emerald-300 bg-emerald-100 text-emerald-950"
                  : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
              }`}
            >
              👁️ {isAnswerOpen ? "Hide answer" : "View answer"}
            </button>
          </div>
        </div>

        {/* Card footer: "Was this exam question helpful? [Yes] [No]" + next question */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 bg-white px-4 py-2 text-[11px] text-slate-500">
          <div className="flex items-center gap-2">
            <span>Was this exam question helpful?</span>
            <button
              type="button"
              onClick={() => setHelpfulVote((prev) => ({ ...prev, [item.uid]: "yes" }))}
              className={`rounded-md border px-2 py-0.5 font-semibold cursor-pointer transition ${
                vote === "yes"
                  ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                  : "border-slate-200 hover:bg-slate-50"
              }`}
            >
              👍 Yes
            </button>
            <button
              type="button"
              onClick={() => setHelpfulVote((prev) => ({ ...prev, [item.uid]: "no" }))}
              className={`rounded-md border px-2 py-0.5 font-semibold cursor-pointer transition ${
                vote === "no"
                  ? "border-rose-300 bg-rose-50 text-rose-800"
                  : "border-slate-200 hover:bg-slate-50"
              }`}
            >
              👎 No
            </button>
          </div>

          {!inModal && qNum < visibleItems.length && (
            <button
              type="button"
              onClick={() => jumpToQuestion(qNum + 1)}
              className="font-fun font-bold text-teal-700 hover:underline cursor-pointer"
            >
              Next question (#{difficultyTab}-{qNum + 1}) →
            </button>
          )}
        </div>
      </article>
    );
  }

  return (
    <div className="space-y-4">
      {/* Topic questions header */}
      <div className="rounded-3xl border-2 border-slate-200 bg-white p-5 md:p-6 shadow-2xs space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-teal-700">
              <span className="rounded-md bg-teal-50 border border-teal-200 px-2 py-0.5 font-fun font-bold">
                Cambridge (CIE) IGCSE {subjectName}
              </span>
              {syllabusCode && (
                <span className="rounded-md bg-slate-100 px-2 py-0.5 text-slate-700 font-bold">
                  Exam code: {syllabusCode}
                </span>
              )}
              <span className="text-slate-400">·</span>
              <span>Topic {topicCode}</span>
            </div>
            <h2 className="text-xl md:text-2xl font-fun font-bold text-slate-900">
              {topicName}: Topic Questions
            </h2>
          </div>

          {/* Right Metadata Pills */}
          <div className="flex flex-wrap items-center gap-2 text-xs font-semibold">
            <span className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-slate-700">
              ⏱️ {estDisplay}
            </span>
            <span className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-slate-700">
              📋 {allItems.length} questions ({totalMarks} marks)
            </span>
            <span className="rounded-xl border border-teal-200 bg-teal-50 px-3 py-1.5 text-teal-900 font-bold">
              ✓ {Object.keys(scores).length} attempted · {totalAwarded} marks earned
            </span>
            <button
              type="button"
              onClick={() => setSavedOnly(!savedOnly)}
              className={`rounded-xl border px-3 py-1.5 font-fun font-bold cursor-pointer transition ${
                savedOnly
                  ? "border-amber-300 bg-amber-100 text-amber-950"
                  : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
              }`}
            >
              🔖 Saved ({savedIds.length})
            </button>
          </div>
        </div>

        {/* Question Format / Paper Type Tabs */}
        <div className="flex flex-wrap items-center gap-1.5 border-t border-slate-100 pt-3">
          {categoryTabs.map((tab) => {
            const active = categoryFilter === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => {
                  setCategoryFilter(tab.key);
                  setActiveNumber(1);
                }}
                className={`rounded-xl px-3.5 py-2 text-xs font-fun font-bold transition cursor-pointer ${
                  active
                    ? "bg-slate-900 text-white shadow-2xs"
                    : "bg-slate-100/80 text-slate-600 hover:bg-slate-200/70 hover:text-slate-900"
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Sticky difficulty bar (Easy | Medium | Hard) + numbered question jump strip (#easy-1, #easy-2...) */}
      <div className="sticky top-2 z-20 rounded-2xl border-2 border-slate-200/90 bg-white/95 backdrop-blur-md p-3 shadow-sm space-y-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          {/* Easy / Medium / Hard Segmented Control */}
          <div className="inline-flex rounded-xl bg-slate-100 p-1">
            {(["easy", "medium", "hard"] as const).map((tier) => {
              const active = difficultyTab === tier;
              const count = countsByDifficulty[tier];
              const label = tier === "easy" ? "Easy" : tier === "medium" ? "Medium" : "Hard";
              const dotColor =
                tier === "easy"
                  ? "bg-emerald-500"
                  : tier === "medium"
                  ? "bg-amber-500"
                  : "bg-rose-500";
              return (
                <button
                  key={tier}
                  type="button"
                  onClick={() => {
                    setDifficultyTab(tier);
                    setActiveNumber(1);
                    window.history.replaceState(null, "", `#${tier}-1`);
                  }}
                  className={`flex items-center gap-2 rounded-lg px-4 py-1.5 text-xs font-fun font-bold transition cursor-pointer ${
                    active
                      ? "bg-white text-slate-900 shadow-2xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  <span className={`h-2 w-2 rounded-full ${dotColor}`} />
                  <span>{label}</span>
                  <span className="rounded-full bg-slate-200/80 px-1.5 py-0.2 text-[10px] text-slate-700">
                    {count}
                  </span>
                </button>
              );
            })}
          </div>

          <span className="text-[11px] font-semibold text-slate-500 hidden md:inline">
            Click a question number to jump directly (e.g. <code className="rounded bg-slate-100 px-1.5 py-0.5 text-teal-800">#{difficultyTab}-{activeNumber}</code>)
          </span>
        </div>

        {/* Numbered Question Jump Strip: 1  2  3  4  5  6  7 ... */}
        {visibleItems.length > 0 && (
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
            {visibleItems.map((item, idx) => {
              const num = idx + 1;
              const isCurrent = activeNumber === num;
              const sc = scores[item.uid];
              const isSaved = savedIds.includes(item.uid);
              const fullMarks = sc && sc.awarded >= sc.available;
              const attempted = sc !== undefined;

              return (
                <button
                  key={item.uid}
                  type="button"
                  onClick={() => jumpToQuestion(num)}
                  className={`relative flex h-8 min-w-8 items-center justify-center rounded-lg border px-2 text-xs font-fun font-bold transition cursor-pointer ${
                    isCurrent
                      ? "border-teal-600 bg-teal-600 text-white shadow-2xs"
                      : fullMarks
                      ? "border-emerald-300 bg-emerald-50 text-emerald-900 hover:bg-emerald-100"
                      : attempted
                      ? "border-amber-300 bg-amber-50 text-amber-900 hover:bg-amber-100"
                      : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50"
                  }`}
                  title={`Jump to #${difficultyTab}-${num} (${item.marks} marks)`}
                >
                  <span>{num}</span>
                  {fullMarks && !isCurrent && (
                    <span className="ml-0.5 text-[10px] text-emerald-600">✓</span>
                  )}
                  {isSaved && (
                    <span className="absolute -top-1 -right-1 h-2 w-2 rounded-full bg-amber-500" />
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Question Cards List */}
      {visibleItems.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          No questions match this filter yet. Try switching the difficulty tab or question format tab above.
        </div>
      ) : (
        <div className="space-y-5">
          {visibleItems.map((item, idx) => renderQuestionCard(item, idx, false))}
        </div>
      )}

      {/* Full-screen overlay */}
      {fullscreenItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 p-4 backdrop-blur-xs">
          <div className="max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-3xl bg-slate-100 p-4 md:p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-fun font-bold uppercase tracking-wider text-slate-600">
                ⛶ Full Screen Exam Focus · {topicName}
              </span>
              <button
                type="button"
                onClick={() => setFullscreenItem(null)}
                className="rounded-xl bg-slate-900 px-3.5 py-1.5 text-xs font-fun font-bold text-white hover:bg-slate-800 cursor-pointer"
              >
                ✕ Exit full screen
              </button>
            </div>
            {renderQuestionCard(fullscreenItem.item, fullscreenItem.index, true)}
          </div>
        </div>
      )}
    </div>
  );
}
