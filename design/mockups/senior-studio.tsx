"use client";

import Link from "next/link";
import { useState } from "react";
import { MathText } from "@/components/MathText";

type ThemePreset = "allen" | "bhanzu" | "midnight";
type DemoScreen = "dashboard" | "notes" | "questions" | "sprint";
type DemoSubject = "sociology" | "maths";
type Difficulty = "easy" | "medium" | "hard";

const THEME_CONFIG: Record<
  ThemePreset,
  {
    name: string;
    badge: string;
    subtitle: string;
    bgPage: string;
    bgSidebar: string;
    bgCard: string;
    borderCard: string;
    textPrimary: string;
    textSecondary: string;
    heroBg: string;
    accentPrimary: string;
    accentSecondary: string;
    pillBg: string;
    pillText: string;
  }
> = {
  allen: {
    name: "ALLEN Overseas Pro",
    badge: "🏛️ High-Performance Academic LMS",
    subtitle: "Crisp Royal Navy, Electric Cobalt & Emerald — engineered for IGCSE Extended & IIT Foundation rigour",
    bgPage: "bg-[#F4F7FB]",
    bgSidebar: "bg-[#0B1528] text-slate-100",
    bgCard: "bg-white",
    borderCard: "border-slate-200/90",
    textPrimary: "text-slate-900",
    textSecondary: "text-slate-500",
    heroBg: "bg-gradient-to-r from-[#0B1528] via-[#13294B] to-[#1E3A8A] text-white",
    accentPrimary: "bg-[#2563EB] hover:bg-[#1D4ED8] text-white",
    accentSecondary: "bg-emerald-500 hover:bg-emerald-600 text-white",
    pillBg: "bg-blue-50 border-blue-200",
    pillText: "text-blue-700",
  },
  bhanzu: {
    name: "Bhanzu Neo-Velocity",
    badge: "⚡ Interactive Mastery & Cognitive Sprints",
    subtitle: "Deep Cosmic Indigo, Electric Violet & Mint — energetic, habit-forming, and zero math anxiety",
    bgPage: "bg-[#F6F5FF]",
    bgSidebar: "bg-[#161233] text-slate-100",
    bgCard: "bg-white",
    borderCard: "border-indigo-100",
    textPrimary: "text-slate-900",
    textSecondary: "text-slate-500",
    heroBg: "bg-gradient-to-r from-[#1E1B4B] via-[#312E81] to-[#4C1D95] text-white",
    accentPrimary: "bg-[#6D28D9] hover:bg-[#5B21B6] text-white",
    accentSecondary: "bg-[#10B981] hover:bg-[#059669] text-white",
    pillBg: "bg-violet-50 border-violet-200",
    pillText: "text-violet-700",
  },
  midnight: {
    name: "Dark Focus Studio",
    badge: "🌙 Senior Student Late-Study Mode",
    subtitle: "Obsidian Slate, Cyan Telemetry & Low-Glare Contrast — built for deep focus exam sessions",
    bgPage: "bg-[#090D16]",
    bgSidebar: "bg-[#0F172A] text-slate-100 border-r border-slate-800",
    bgCard: "bg-[#111827]",
    borderCard: "border-slate-800",
    textPrimary: "text-slate-100",
    textSecondary: "text-slate-400",
    heroBg: "bg-gradient-to-r from-[#0F172A] via-[#1E293B] to-[#0F172A] text-white border border-slate-700",
    accentPrimary: "bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold",
    accentSecondary: "bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold",
    pillBg: "bg-slate-800 border-slate-700",
    pillText: "text-cyan-400",
  },
};

const DEMO_QUESTIONS = {
  sociology: {
    subjectTitle: "Cambridge IGCSE Sociology (0495)",
    topicCode: "1.1.1",
    topicTitle: "Positivism, Interpretivism & Scientific Method",
    easy: [
      {
        num: 1,
        paper: "June 2024 · Paper 12 · Q1(a)",
        tier: "Paper 1 · Research Methods",
        command: "Identify",
        marks: 2,
        stem: "From Source A, identify two quantitative research methods used by positivist sociologists.",
        context:
          "Source A: Positivist sociologists prefer macro-level research using official crime statistics and large-scale structured questionnaires to uncover social patterns across thousands of citizens.",
        help: [
          "For a 2-mark 'Identify two' question, write two distinct methods directly from the source — no long intro needed.",
          "Both 'official statistics' and 'structured questionnaires / surveys' earn 1 mark each.",
        ],
        answer: [
          "1. Official statistics / crime statistics [1 mark]",
          "2. Large-scale structured questionnaires / social surveys [1 mark]",
        ],
      },
      {
        num: 2,
        paper: "Nov 2024 · Paper 11 · Q1(b)",
        tier: "Paper 1 · Research Methods",
        command: "Describe",
        marks: 4,
        stem: "Describe two strengths of using structured questionnaires in sociological research.",
        context: null,
        help: [
          "4 marks = 2 × (Point + Development).",
          "Strength 1: High reliability — standardized closed questions allow other researchers to replicate the study and check for consistent patterns.",
          "Strength 2: Large representative samples — practical and quick to distribute to thousands of respondents, allowing positivists to generalize findings.",
        ],
        answer: [
          "Point 1: High reliability [1] because every respondent answers the exact same standardized questions, making replication easy [1].",
          "Point 2: Large sample size / representativeness [1], allowing sociologists to uncover macro-level statistical correlations and generalize [1].",
        ],
      },
    ],
    medium: [
      {
        num: 1,
        paper: "June 2024 · Paper 12 · Q1(d)",
        tier: "Paper 1 · Structured Explain",
        command: "Explain",
        marks: 6,
        stem: "Explain why interpretivist sociologists reject the use of natural science methods to study human society.",
        context: null,
        help: [
          "6 marks = 3 developed PEEL paragraphs (2 marks each).",
          "Anchor in key concepts: Verstehen (Weber), social construction of meanings, and invalidity of artificial lab/closed-survey methods.",
        ],
        answer: [
          "1. Consciousness & Free Will: Unlike atoms or chemicals in natural science, human beings have agency and attach subjective meanings to their actions [2].",
          "2. Need for Verstehen (Empathy): Weber argued sociologists must put themselves in the shoes of actors using qualitative methods (unstructured interviews/observation) to achieve validity [2].",
          "3. Rejection of Official Statistics: Interpretivists view official statistics as social constructs reflecting police/state labels rather than objective 'social facts' [2].",
        ],
      },
    ],
    hard: [
      {
        num: 1,
        paper: "June 2024 · Paper 12 · Q1(e)",
        tier: "Paper 1 · Extended Evaluation Essay",
        command: "To what extent",
        marks: 14,
        stem: "To what extent is the positivist approach the most effective way to discover valid truth about society?",
        context: null,
        help: [
          "14 marks = Balanced two-sided debate (3 arguments FOR Positivism + 3 arguments AGAINST from Interpretivism/Feminism) + reasoned Conclusion.",
          "Cite Durkheim (social facts, suicide study) on the For side; cite Weber (Verstehen) and Atkinson (coroners' construction of suicide) on the Against side.",
        ],
        answer: [
          "FOR Positivism (Durkheim): Macro patterns, objectivity, reliability, large representative samples uncover structural causes (e.g., social integration in Le Suicide) [6 marks].",
          "AGAINST (Interpretivism / Realism): Lacks depth/validity, ignores subjective meanings (Verstehen), respondent deceit in questionnaires, official stats are socially constructed [6 marks].",
          "EVALUATIVE CONCLUSION: Methodological pluralists combine both — quantitative surveys map the macro trend while qualitative interviews explain the human 'why' behind it [2 marks].",
        ],
      },
    ],
  },
  maths: {
    subjectTitle: "Cambridge IGCSE Extended Mathematics (0580)",
    topicCode: "2.5",
    topicTitle: "Quadratic Equations, Factorisation & Completing the Square",
    easy: [
      {
        num: 1,
        paper: "June 2024 · Paper 22 · Q9",
        tier: "Extended Tier · Paper 2 Short",
        command: "Solve",
        marks: 2,
        stem: "Solve by factorising: $x^2 - 7x + 12 = 0$.",
        context: null,
        help: [
          "Find two numbers that multiply to $+12$ and add to $-7$.",
          "Those numbers are $-3$ and $-4$, giving $(x - 3)(x - 4) = 0$.",
        ],
        answer: [
          "Factorise into brackets: $(x - 3)(x - 4) = 0$ [M1]",
          "Roots: $x = 3$ or $x = 4$ [A1]",
        ],
      },
      {
        num: 2,
        paper: "Nov 2024 · Paper 21 · Q14",
        tier: "Extended Tier · Paper 2 Short",
        command: "Factorise",
        marks: 2,
        stem: "Factorise completely: $2x^2 - 18$.",
        context: null,
        help: [
          "Step 1: Always take out the highest common numerical factor first ($2$).",
          "Step 2: Recognise the Difference of Two Squares ($x^2 - 9 = x^2 - 3^2$).",
        ],
        answer: [
          "Take out common factor $2$: $2(x^2 - 9)$ [B1]",
          "Difference of two squares: $2(x - 3)(x + 3)$ [B1]",
        ],
      },
    ],
    medium: [
      {
        num: 1,
        paper: "June 2024 · Paper 42 · Q4(b)",
        tier: "Extended Tier · Paper 4",
        command: "Write in the form",
        marks: 3,
        stem: "Write $x^2 - 6x + 14$ in the completed square form $(x - p)^2 + q$, and hence state the coordinates of the turning point of $y = x^2 - 6x + 14$.",
        context: null,
        help: [
          "Halve the coefficient of $x$: half of $-6$ is $-3$, so start with $(x - 3)^2$.",
          "Subtract $(-3)^2 = 9$ and add $14$: $(x - 3)^2 - 9 + 14 = (x - 3)^2 + 5$.",
        ],
        answer: [
          "Completed square form: $(x - 3)^2 + 5$ [B2: B1 for $(x - 3)^2$, B1 for $+ 5$]",
          "Minimum turning point: $(3, 5)$ [B1]",
        ],
      },
    ],
    hard: [
      {
        num: 1,
        paper: "June 2024 · Paper 41 · Q8(c) · IIT Bridge",
        tier: "Extended Tier · Paper 4 Multi-Step",
        command: "Calculate",
        marks: 5,
        stem: "A right-angled triangle has base $(2x + 1)\\text{ cm}$, perpendicular height $(x - 2)\\text{ cm}$, and area $17\\text{ cm}^2$. Show that $2x^2 - 3x - 36 = 0$ and find the length of the base correct to 2 decimal places.",
        context: null,
        help: [
          "Use $\\text{Area} = \\frac{1}{2} \\times \\text{base} \\times \\text{height} = 17$.",
          "Multiply both sides by $2$: $(2x + 1)(x - 2) = 34$, expand to reach $2x^2 - 3x - 36 = 0$.",
          "Apply the quadratic formula $x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$, reject $x < 2$, and substitute into $2x + 1$.",
        ],
        answer: [
          "$\\frac{1}{2}(2x + 1)(x - 2) = 17 \\Rightarrow 2x^2 - 4x + x - 2 = 34 \\Rightarrow 2x^2 - 3x - 36 = 0$ [M2]",
          "$x = \\frac{3 \\pm \\sqrt{(-3)^2 - 4(2)(-36)}}{4} = \\frac{3 \\pm \\sqrt{297}}{4}$ [M1]",
          "Positive root $x = 5.0584...\\text{ cm}$ (reject negative root since $x > 2$) [A1]",
          "Base $= 2(5.0584...) + 1 = 11.12\\text{ cm}$ (2 d.p.) [B1]",
        ],
      },
    ],
  },
};

export default function SeniorRevampDemoPage() {
  const [themeKey, setThemeKey] = useState<ThemePreset>("allen");
  const [screen, setScreen] = useState<DemoScreen>("dashboard");
  const [subject, setSubject] = useState<DemoSubject>("sociology");
  const [difficulty, setDifficulty] = useState<Difficulty>("easy");
  const [qIndex, setQIndex] = useState<number>(0);
  const [showHelp, setShowHelp] = useState<boolean>(false);
  const [showAnswer, setShowAnswer] = useState<boolean>(false);
  const [showMarker, setShowMarker] = useState<boolean>(false);
  const [draftAnswer, setDraftAnswer] = useState<string>("");
  const [selfScored, setSelfScored] = useState<Record<string, number>>({
    "sociology-easy-0": 2,
    "maths-easy-0": 2,
  });
  const [cheatSheetMode, setCheatSheetMode] = useState<boolean>(false);
  const [sprintScore, setSprintScore] = useState<number>(3);
  const [sprintStep, setSprintStep] = useState<number>(0);

  const theme = THEME_CONFIG[themeKey];
  const currentTopic = DEMO_QUESTIONS[subject];
  const questionList = currentTopic[difficulty];
  const activeQuestion = questionList[qIndex] ?? questionList[0];
  const scoreKey = `${subject}-${difficulty}-${qIndex}`;

  const SPRINT_DRILLS = [
    {
      q: "If $\\alpha$ and $\\beta$ are roots of $x^2 - 9x + 20 = 0$, what is $\\alpha + \\beta$?",
      options: ["$-9$", "$9$", "$20$", "$4$"],
      correct: 1,
      tag: "IIT Foundation · Vieta's Shortcut (5 sec)",
    },
    {
      q: "Which sociological perspective views official crime statistics as socially constructed labels?",
      options: ["Positivism", "Interpretivism", "Functionalism", "Biological Determinism"],
      correct: 1,
      tag: "IGCSE Sociology 0495 · Rapid Concept Check",
    },
    {
      q: "What is the turning point of $y = (x - 4)^2 - 7$?",
      options: ["$(-4, -7)$", "$(4, 7)$", "$(4, -7)$", "$(-4, 7)$"],
      correct: 2,
      tag: "IGCSE Extended Maths 0580 · Completing the Square",
    },
  ];

  return (
    <div className={`min-h-screen ${theme.bgPage} ${theme.textPrimary} font-sans transition-colors duration-300`}>
      {/* TOP DESIGN REVIEW BAR (Allows parent & daughter to switch themes & screens live) */}
      <div className="sticky top-0 z-50 border-b border-slate-800 bg-[#070B14]/95 text-white backdrop-blur-md px-4 py-2.5 shadow-lg">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="rounded-lg bg-gradient-to-r from-blue-500 to-emerald-400 px-2.5 py-1 text-[11px] font-extrabold uppercase tracking-wider text-slate-950">
              UI/UX Revamp Prototype
            </span>
            <span className="text-xs font-semibold text-slate-300 hidden sm:inline">
              Senior Student Edition (Year 10 IGCSE + IIT Foundation) · Inspired by ALLEN Overseas, Bhanzu & SaveMyExams
            </span>
          </div>

          {/* Theme Preset Switcher */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-semibold text-slate-400 mr-1">Visual Theme:</span>
            {(["allen", "bhanzu", "midnight"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setThemeKey(t)}
                className={`rounded-lg px-3 py-1 text-xs font-bold transition cursor-pointer ${
                  themeKey === t
                    ? "bg-white text-slate-950 shadow-xs"
                    : "bg-slate-800/90 text-slate-300 hover:bg-slate-700"
                }`}
              >
                {t === "allen" ? "🏛️ ALLEN Pro" : t === "bhanzu" ? "⚡ Bhanzu Neo" : "🌙 Dark Focus"}
              </button>
            ))}

            <Link
              href="/student"
              className="ml-2 rounded-lg border border-slate-700 bg-slate-900 px-3 py-1 text-xs font-semibold text-slate-300 hover:bg-slate-800"
            >
              ← Current Portal
            </Link>
          </div>
        </div>
      </div>

      {/* MAIN APP SHELL: Left Senior Sidebar + Right Workspace */}
      <div className="flex min-h-[calc(100vh-49px)]">
        {/* LEFT SIDEBAR: Sleek Dark Navy / Indigo Senior LMS Navigation */}
        <aside className={`hidden lg:flex w-64 flex-col justify-between p-4 ${theme.bgSidebar}`}>
          <div className="space-y-6">
            {/* Brand Header */}
            <div className="flex items-center justify-between px-2 pt-1">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 via-indigo-500 to-emerald-400 font-mono text-lg font-extrabold text-white shadow-md">
                  S
                </div>
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-base font-extrabold tracking-tight text-white">SCHOLR</span>
                    <span className="rounded bg-blue-500/20 border border-blue-400/30 px-1.5 py-0.5 font-mono text-[10px] font-bold text-blue-300">
                      PRO · Y10
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">Cambridge & IIT Studio</p>
                </div>
              </div>
            </div>

            {/* Interactive Screen Switcher in Sidebar */}
            <div className="space-y-1">
              <div className="px-3 pb-1 text-[10px] font-bold uppercase tracking-widest text-slate-400">
                Prototype Screens
              </div>
              {[
                { key: "dashboard", label: "Command Center", icon: "◫", badge: "ALLEN × Bhanzu" },
                { key: "notes", label: "Revision Notes Studio", icon: "📖", badge: "SaveMyExams" },
                { key: "questions", label: "Topic Questions (#easy-2)", icon: "✍️", badge: "Live Marker" },
                { key: "sprint", label: "Speed Gym & IIT Bridge", icon: "⚡", badge: "60s Sprint" },
              ].map((nav) => {
                const active = screen === nav.key;
                return (
                  <button
                    key={nav.key}
                    type="button"
                    onClick={() => setScreen(nav.key as DemoScreen)}
                    className={`flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-xs font-semibold transition cursor-pointer ${
                      active
                        ? "bg-blue-600 text-white shadow-md shadow-blue-600/25"
                        : "text-slate-300 hover:bg-white/5 hover:text-white"
                    }`}
                  >
                    <span className="flex items-center gap-2.5">
                      <span className="text-sm">{nav.icon}</span>
                      <span>{nav.label}</span>
                    </span>
                    <span
                      className={`rounded px-1.5 py-0.5 font-mono text-[10px] ${
                        active ? "bg-blue-800 text-blue-100" : "bg-white/5 text-slate-400"
                      }`}
                    >
                      {nav.badge}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Subject Quick-Switch in Sidebar */}
            <div className="space-y-1.5">
              <div className="px-3 pb-1 text-[10px] font-bold uppercase tracking-widest text-slate-400">
                Active Subject Lens
              </div>
              <button
                type="button"
                onClick={() => {
                  setSubject("sociology");
                  setQIndex(0);
                }}
                className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-xs font-semibold transition cursor-pointer ${
                  subject === "sociology"
                    ? "bg-emerald-500/20 border border-emerald-400/40 text-emerald-300"
                    : "text-slate-400 hover:bg-white/5"
                }`}
              >
                <span>🏛️ IGCSE Sociology</span>
                <span className="font-mono text-[11px]">0495</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setSubject("maths");
                  setQIndex(0);
                }}
                className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-xs font-semibold transition cursor-pointer ${
                  subject === "maths"
                    ? "bg-emerald-500/20 border border-emerald-400/40 text-emerald-300"
                    : "text-slate-400 hover:bg-white/5"
                }`}
              >
                <span>📐 Extended Maths</span>
                <span className="font-mono text-[11px]">0580</span>
              </button>
            </div>

            {/* Senior Student Telemetry Mini-Widget */}
            <div className="rounded-2xl border border-white/10 bg-white/5 p-3.5 space-y-2.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-white">🔥 12-Day Streak</span>
                <span className="font-mono text-[11px] text-emerald-400">+140 XP today</span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                <div className="h-full w-4/5 rounded-full bg-gradient-to-r from-blue-500 to-emerald-400" />
              </div>
              <div className="flex justify-between font-mono text-[10px] text-slate-400">
                <span>Weekly Target: 4.5 / 5.5 hrs</span>
                <span className="text-emerald-400">82%</span>
              </div>
            </div>
          </div>

          {/* Bottom AI Co-Pilot Status */}
          <div className="rounded-2xl border border-blue-500/30 bg-gradient-to-br from-blue-950/80 to-indigo-950/80 p-3.5">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-xs font-bold text-white">Scholr AI Mentor Online</span>
            </div>
            <p className="mt-1 text-[11px] text-slate-300 leading-relaxed">
              Dual-verified with SymPy & Cambridge 2026 Mark Schemes.
            </p>
          </div>
        </aside>

        {/* RIGHT MAIN WORKSPACE */}
        <div className="flex-1 min-w-0">
          {/* Sub-Header Bar with Screen Tabs & Subject Switcher */}
          <header
            className={`border-b ${theme.borderCard} ${theme.bgCard} px-4 md:px-8 py-3.5 flex flex-wrap items-center justify-between gap-3`}
          >
            {/* Screen Switcher Pills */}
            <div className="flex flex-wrap items-center gap-1.5">
              {[
                { key: "dashboard", label: "1. Command Dashboard" },
                { key: "notes", label: "2. Revision Notes Studio" },
                { key: "questions", label: "3. Topic Questions (#easy-2)" },
                { key: "sprint", label: "4. Bhanzu Sprint & IIT Tracker" },
              ].map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setScreen(tab.key as DemoScreen)}
                  className={`rounded-xl px-3.5 py-2 text-xs font-bold transition cursor-pointer ${
                    screen === tab.key
                      ? theme.accentPrimary
                      : `border ${theme.borderCard} ${theme.textSecondary} hover:opacity-90`
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Subject Toggle Pill (Sociology 0495 vs Mathematics 0580) */}
            <div className="flex items-center gap-1.5 rounded-xl border border-slate-300/80 bg-slate-100/80 p-1 text-xs text-slate-800">
              <button
                type="button"
                onClick={() => {
                  setSubject("sociology");
                  setQIndex(0);
                }}
                className={`rounded-lg px-3 py-1.5 font-bold transition cursor-pointer ${
                  subject === "sociology" ? "bg-slate-900 text-white shadow-2xs" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Sociology (0495)
              </button>
              <button
                type="button"
                onClick={() => {
                  setSubject("maths");
                  setQIndex(0);
                }}
                className={`rounded-lg px-3 py-1.5 font-bold transition cursor-pointer ${
                  subject === "maths" ? "bg-slate-900 text-white shadow-2xs" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Mathematics (0580)
              </button>
            </div>
          </header>

          <main className="mx-auto max-w-6xl p-4 md:p-8 space-y-6">
            {/* =====================================================================
                SCREEN 1: ALLEN OVERSEAS × BHANZU SENIOR COMMAND DASHBOARD
               ===================================================================== */}
            {screen === "dashboard" && (
              <div className="space-y-6">
                {/* HERO MISSION CARD */}
                <div className={`rounded-3xl p-6 md:p-8 shadow-xl ${theme.heroBg}`}>
                  <div className="flex flex-wrap items-start justify-between gap-6">
                    <div className="space-y-3 max-w-2xl">
                      <div className="inline-flex items-center gap-2 rounded-full bg-white/10 border border-white/15 px-3 py-1 text-xs font-semibold text-blue-200">
                        <span>🎯 YEAR 10 ACADEMIC COMMAND CENTER</span>
                        <span>·</span>
                        <span className="font-mono text-emerald-300">CAMBRIDGE CIE + ALLEN IIT BRIDGE</span>
                      </div>
                      <h1 className="text-2xl md:text-4xl font-extrabold tracking-tight">
                        Welcome back. Ready for today&apos;s 25-minute high-yield sprint?
                      </h1>
                      <p className="text-sm text-slate-300 leading-relaxed">
                        No clutter, no guesswork. Pick up right where you left off in{" "}
                        <strong className="text-white">{currentTopic.subjectTitle}</strong> or launch a 5-minute
                        Bhanzu-style speed drill.
                      </p>

                      <div className="flex flex-wrap items-center gap-3 pt-2">
                        <button
                          type="button"
                          onClick={() => {
                            setScreen("questions");
                            setDifficulty("easy");
                            setQIndex(1);
                          }}
                          className="rounded-xl bg-emerald-500 hover:bg-emerald-400 px-5 py-3 text-xs md:text-sm font-extrabold text-slate-950 shadow-lg shadow-emerald-500/20 transition cursor-pointer"
                        >
                          ▶ Resume Topic {currentTopic.topicCode} Questions (#easy-2) →
                        </button>
                        <button
                          type="button"
                          onClick={() => setScreen("notes")}
                          className="rounded-xl border border-white/20 bg-white/10 hover:bg-white/15 px-4 py-3 text-xs md:text-sm font-bold text-white transition cursor-pointer"
                        >
                          📖 Open {subject === "sociology" ? "Sociology" : "Maths"} Revision Notes
                        </button>
                        <button
                          type="button"
                          onClick={() => setScreen("sprint")}
                          className="rounded-xl border border-violet-400/40 bg-violet-500/20 hover:bg-violet-500/30 px-4 py-3 text-xs md:text-sm font-bold text-violet-200 transition cursor-pointer"
                        >
                          ⚡ 60s Brain Gym Sprint
                        </button>
                      </div>
                    </div>

                    {/* Right Telemetry Ring Card (ALLEN Overseas Test-Prep Style) */}
                    <div className="w-full sm:w-72 rounded-2xl border border-white/15 bg-white/10 backdrop-blur-md p-4 space-y-3">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-bold uppercase tracking-wider text-slate-300">Today&apos;s Action Plan</span>
                        <span className="font-mono font-bold text-emerald-300">2 / 3 Done</span>
                      </div>
                      <div className="space-y-2 text-xs">
                        <div className="flex items-center justify-between rounded-xl bg-white/10 px-3 py-2">
                          <span className="flex items-center gap-2">
                            <span className="text-emerald-400 font-bold">✓</span>
                            <span>Sociology 1.1.1 Revision Notes</span>
                          </span>
                          <span className="font-mono text-[11px] text-slate-300">12m</span>
                        </div>
                        <div className="flex items-center justify-between rounded-xl bg-emerald-500/20 border border-emerald-400/40 px-3 py-2 font-semibold text-white">
                          <span className="flex items-center gap-2">
                            <span className="text-amber-300">▶</span>
                            <span>Topic Qs: Easy → Medium</span>
                          </span>
                          <span className="font-mono text-[11px] text-emerald-300">Now</span>
                        </div>
                        <div className="flex items-center justify-between rounded-xl bg-white/5 px-3 py-2 text-slate-300">
                          <span className="flex items-center gap-2">
                            <span>○</span>
                            <span>Maths 0580 Quadratic Drill</span>
                          </span>
                          <span className="font-mono text-[11px]">10m</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* ALLEN OVERSEAS ANALYTICAL TELEMETRY STRIP */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {[
                    {
                      label: "SYLLABUS MASTERY",
                      value: "81 / 81",
                      sub: "Sociology 0495 Lessons Ready (v6)",
                      badge: "100% Grounded",
                      tone: "text-emerald-600 bg-emerald-50 border-emerald-200",
                    },
                    {
                      label: "MATHS 0580 EXTENDED",
                      value: "189 / 189",
                      sub: "SymPy-Verified Worked Topics",
                      badge: "Paper 2 & 4",
                      tone: "text-blue-600 bg-blue-50 border-blue-200",
                    },
                    {
                      label: "EXAM MARK ACCURACY",
                      value: "78.4%",
                      sub: "+6.2% vs last 14 days",
                      badge: "A / A* Band",
                      tone: "text-violet-600 bg-violet-50 border-violet-200",
                    },
                    {
                      label: "INDEPENDENT SOLVING",
                      value: "84%",
                      sub: "Solved without hints",
                      badge: "High Autonomy",
                      tone: "text-amber-700 bg-amber-50 border-slate-200",
                    },
                  ].map((stat, idx) => (
                    <div
                      key={idx}
                      className={`rounded-2xl border ${theme.borderCard} ${theme.bgCard} p-4 shadow-2xs space-y-2`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[11px] font-bold tracking-wider text-slate-400">
                          {stat.label}
                        </span>
                        <span className={`rounded-md border px-2 py-0.5 text-[10px] font-bold ${stat.tone}`}>
                          {stat.badge}
                        </span>
                      </div>
                      <div className="font-mono text-2xl font-extrabold">{stat.value}</div>
                      <p className={`text-xs ${theme.textSecondary}`}>{stat.sub}</p>
                    </div>
                  ))}
                </div>

                {/* DUAL-STREAM SUBJECT BENTO GRID */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                  {/* Left 2 Columns: Cambridge IGCSE Core Subjects */}
                  <div className={`lg:col-span-2 rounded-2xl border ${theme.borderCard} ${theme.bgCard} p-5 space-y-4`}>
                    <div className="flex items-center justify-between">
                      <div>
                        <h2 className="text-base font-extrabold">Cambridge IGCSE Extended Stream</h2>
                        <p className={`text-xs ${theme.textSecondary}`}>
                          Direct 1-click access to SaveMyExams-style Revision Notes & Topic Questions
                        </p>
                      </div>
                      <span className="font-mono text-xs font-bold text-blue-600">2026–2027 Syllabus</span>
                    </div>

                    <div className="space-y-3">
                      {[
                        {
                          code: "0495",
                          name: "IGCSE Sociology",
                          topics: "81 topics · 1,491 Past-Paper Qs",
                          pct: 68,
                          key: "sociology" as DemoSubject,
                          highlight: "Paper 1 & 2 · PEEL & Evaluation Essays",
                        },
                        {
                          code: "0580",
                          name: "IGCSE Extended Mathematics",
                          topics: "189 topics · 668 Past-Paper Qs + SymPy Drills",
                          pct: 74,
                          key: "maths" as DemoSubject,
                          highlight: "Paper 2 (Non-Calc) & Paper 4 (Extended)",
                        },
                      ].map((subj) => (
                        <div
                          key={subj.code}
                          className={`rounded-2xl border ${theme.borderCard} p-4 transition hover:border-blue-400`}
                        >
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div className="space-y-1">
                              <div className="flex items-center gap-2">
                                <span className="rounded-lg bg-slate-900 px-2 py-0.5 font-mono text-xs font-bold text-white">
                                  {subj.code}
                                </span>
                                <span className="text-base font-extrabold">{subj.name}</span>
                              </div>
                              <p className={`text-xs ${theme.textSecondary}`}>
                                {subj.topics} · <span className="font-semibold text-blue-600">{subj.highlight}</span>
                              </p>
                            </div>

                            <div className="flex items-center gap-2">
                              <button
                                type="button"
                                onClick={() => {
                                  setSubject(subj.key);
                                  setScreen("notes");
                                }}
                                className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-bold text-slate-800 hover:bg-slate-100 cursor-pointer"
                              >
                                📖 Revision Notes
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  setSubject(subj.key);
                                  setScreen("questions");
                                }}
                                className={`rounded-xl px-3.5 py-2 text-xs font-bold cursor-pointer ${theme.accentPrimary}`}
                              >
                                ✍️ Topic Questions (#easy-1)
                              </button>
                            </div>
                          </div>

                          <div className="mt-3 flex items-center gap-3">
                            <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200">
                              <div
                                className="h-full rounded-full bg-gradient-to-r from-blue-600 to-emerald-500"
                                style={{ width: `${subj.pct}%` }}
                              />
                            </div>
                            <span className="font-mono text-xs font-bold text-slate-600">{subj.pct}% Mastered</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Right Column: ALLEN Overseas Style IIT Foundation Tracker */}
                  <div className={`rounded-2xl border ${theme.borderCard} ${theme.bgCard} p-5 space-y-4`}>
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="rounded bg-amber-500/15 border border-amber-500/30 px-2 py-0.5 font-mono text-[10px] font-bold text-amber-600">
                          ALLEN OVERSEAS STYLE
                        </span>
                        <h2 className="mt-1 text-base font-extrabold">IIT Foundation Bridge</h2>
                      </div>
                      <button
                        type="button"
                        onClick={() => setScreen("sprint")}
                        className="text-xs font-bold text-blue-600 hover:underline cursor-pointer"
                      >
                        Open Hub →
                      </button>
                    </div>

                    <p className={`text-xs ${theme.textSecondary} leading-relaxed`}>
                      Maps every coaching class & test back to the IGCSE Extended concepts underneath it.
                    </p>

                    <div className="space-y-2.5 text-xs">
                      {[
                        {
                          subject: "IIT Mathematics",
                          topic: "Quadratic Roots & Vieta's Formulas",
                          score: "28 / 30",
                          status: "Strong",
                        },
                        {
                          subject: "IIT Physics",
                          topic: "Kinematics & Vector Resolution",
                          score: "22 / 30",
                          status: "Warm-up Ready",
                        },
                        {
                          subject: "IIT Chemistry",
                          topic: "Mole Concept & Stoichiometry",
                          score: "26 / 30",
                          status: "Strong",
                        },
                      ].map((row, i) => (
                        <div key={i} className={`rounded-xl border ${theme.borderCard} p-3 space-y-1`}>
                          <div className="flex items-center justify-between font-bold">
                            <span>{row.subject}</span>
                            <span className="font-mono text-emerald-600">{row.score}</span>
                          </div>
                          <div className="flex items-center justify-between text-[11px] text-slate-500">
                            <span>{row.topic}</span>
                            <span className="font-semibold text-blue-600">{row.status}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* BEFORE VS AFTER UI COMPARISON CARD FOR REVIEW */}
                <div className={`rounded-2xl border ${theme.borderCard} ${theme.bgCard} p-5 space-y-3`}>
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-extrabold uppercase tracking-wider text-blue-600">
                      ✨ What Changed in This Senior Student UI/UX Revamp?
                    </h3>
                    <span className="font-mono text-xs text-slate-400">Design System v2.0</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                    <div className="rounded-xl bg-slate-50 dark:bg-slate-900/50 p-3.5 border border-slate-200/80 space-y-1">
                      <div className="font-bold text-slate-900">1. Senior Typography & Contrast</div>
                      <p className="text-slate-600 leading-relaxed">
                        Replaced the primary-school <code>Fredoka</code> cursive font and warm beige background with
                        crisp geometric sans + <code>JetBrains Mono</code> telemetry for exam codes, timers, and marks.
                      </p>
                    </div>
                    <div className="rounded-xl bg-slate-50 dark:bg-slate-900/50 p-3.5 border border-slate-200/80 space-y-1">
                      <div className="font-bold text-slate-900">2. ALLEN × SaveMyExams Precision</div>
                      <p className="text-slate-600 leading-relaxed">
                        Structured syllabus trees, <code>Easy | Medium | Hard</code> segmented question bars, numbered
                        jump pills (<code>#easy-2</code>), and instant Cambridge rubric coaching.
                      </p>
                    </div>
                    <div className="rounded-xl bg-slate-50 dark:bg-slate-900/50 p-3.5 border border-slate-200/80 space-y-1">
                      <div className="font-bold text-slate-900">3. Bhanzu Micro-Sprints & Streaks</div>
                      <p className="text-slate-600 leading-relaxed">
                        Added 60-second rapid concept sprints, live streak/XP telemetry, and 3 selectable visual themes
                        (ALLEN Pro, Bhanzu Neo, and Dark Focus Studio).
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* =====================================================================
                SCREEN 2: SAVEMYEXAMS × ALLEN REVISION NOTES STUDIO
               ===================================================================== */}
            {screen === "notes" && (
              <div className="space-y-5">
                <div className={`rounded-2xl border ${theme.borderCard} ${theme.bgCard} p-5 flex flex-wrap items-center justify-between gap-4`}>
                  <div>
                    <div className="flex items-center gap-2 text-xs font-bold text-blue-600">
                      <span>{currentTopic.subjectTitle}</span>
                      <span>›</span>
                      <span>Topic {currentTopic.topicCode}</span>
                    </div>
                    <h2 className="mt-1 text-xl md:text-2xl font-extrabold">{currentTopic.topicTitle}</h2>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setCheatSheetMode(!cheatSheetMode)}
                      className={`rounded-xl border px-3.5 py-2 text-xs font-bold transition cursor-pointer ${
                        cheatSheetMode
                          ? "bg-amber-500 text-slate-950 border-amber-500"
                          : "border-slate-300 bg-white text-slate-800 hover:bg-slate-100"
                      }`}
                    >
                      {cheatSheetMode ? "📖 Full Coaching Notes" : "⚡ 1-Page Exam Cheat Sheet"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setScreen("questions")}
                      className={`rounded-xl px-4 py-2 text-xs font-bold cursor-pointer ${theme.accentPrimary}`}
                    >
                      ✍️ Test Yourself (#easy-1) →
                    </button>
                  </div>
                </div>

                {subject === "sociology" ? (
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                    <div className={`lg:col-span-2 rounded-2xl border ${theme.borderCard} ${theme.bgCard} p-6 space-y-5`}>
                      <div className="rounded-xl border-l-4 border-l-blue-600 bg-blue-50/70 p-4 text-slate-900">
                        <div className="text-[11px] font-bold uppercase tracking-wider text-blue-800">
                          📌 Key Syllabus Definition (Cambridge 0495)
                        </div>
                        <p className="mt-1 text-sm font-medium leading-relaxed">
                          <strong>Positivism</strong> is a macro-structural approach that argues sociology should study{" "}
                          <strong>social facts</strong> objectively using quantitative methods (structured
                          questionnaires, official statistics) to uncover laws of cause and correlation.
                        </p>
                      </div>

                      {!cheatSheetMode && (
                        <div className="space-y-3">
                          <h3 className="text-base font-extrabold">1. Core Principles of the Positivist Approach</h3>
                          <ul className="space-y-2 text-sm leading-relaxed pl-4 list-disc">
                            <li>
                              <strong>Macro-Structural Focus:</strong> Examines large-scale social institutions (the
                              state, education, economy) that shape individual behaviour from the outside.
                            </li>
                            <li>
                              <strong>Objectivity & Value Freedom:</strong> Researchers must remain detached so personal
                              bias does not distort findings.
                            </li>
                            <li>
                              <strong>Reliability & Replication:</strong> Standardized quantitative data allows other
                              sociologists to repeat the study and verify patterns.
                            </li>
                          </ul>
                        </div>
                      )}

                      {/* Comparison Table */}
                      <div className="overflow-hidden rounded-xl border border-slate-200">
                        <table className="w-full text-left text-xs md:text-sm">
                          <thead className="bg-slate-900 text-white font-bold">
                            <tr>
                              <th className="p-3">Dimension</th>
                              <th className="p-3">Positivism (Durkheim)</th>
                              <th className="p-3">Interpretivism (Weber)</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-200 bg-white text-slate-800">
                            <tr>
                              <td className="p-3 font-bold">Level of Analysis</td>
                              <td className="p-3">Macro (large-scale social structures)</td>
                              <td className="p-3">Micro (small-scale face-to-face interaction)</td>
                            </tr>
                            <tr>
                              <td className="p-3 font-bold">Preferred Data</td>
                              <td className="p-3">Quantitative (stats, closed surveys)</td>
                              <td className="p-3">Qualitative (unstructured interviews, observation)</td>
                            </tr>
                            <tr>
                              <td className="p-3 font-bold">Primary Goal</td>
                              <td className="p-3">Reliability, representativeness & causation</td>
                              <td className="p-3">Validity, depth & Verstehen (empathy)</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>

                      <div className="rounded-xl border border-emerald-300 bg-emerald-50/80 p-4 text-xs md:text-sm text-emerald-950">
                        <span className="font-extrabold">💡 Cambridge 0495 Examiner Tip: </span>
                        Never write that Positivists &ldquo;only care about numbers&rdquo; — state that they use{" "}
                        <strong>quantitative data to discover patterns, correlations, and social facts</strong> (citing
                        Durkheim&apos;s study of suicide).
                      </div>
                    </div>

                    <div className={`rounded-2xl border ${theme.borderCard} ${theme.bgCard} p-5 space-y-4`}>
                      <div className="text-xs font-extrabold uppercase tracking-wider text-blue-600">
                        🎧 Dual-Host Audio & Key Glossary
                      </div>
                      <div className="rounded-xl bg-slate-900 p-4 text-white space-y-2">
                        <div className="text-xs font-bold">Topic 1.1.1 Deep-Dive Podcast</div>
                        <p className="text-[11px] text-slate-300">
                          Listen to a 3-minute breakdown of Durkheim vs. Weber while reviewing the comparison table.
                        </p>
                      </div>
                      <div className="space-y-2 text-xs">
                        {[
                          { term: "Social Facts", def: "External social forces and norms that constrain individual action (Durkheim)." },
                          { term: "Verstehen", def: "Empathetic understanding — seeing the world through the eyes of social actors (Weber)." },
                          { term: "Reliability", def: "Whether a research method produces consistent results when replicated." },
                        ].map((kt, i) => (
                          <div key={i} className={`rounded-xl border ${theme.borderCard} p-3`}>
                            <div className="font-bold">{kt.term}</div>
                            <div className={`mt-0.5 ${theme.textSecondary}`}>{kt.def}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className={`rounded-2xl border ${theme.borderCard} ${theme.bgCard} p-6 space-y-5`}>
                    <div className="rounded-xl border-l-4 border-l-blue-600 bg-blue-50/70 p-4 text-slate-900">
                      <div className="text-[11px] font-bold uppercase tracking-wider text-blue-800">
                        📌 Core Algebraic Identity (Cambridge 0580 Extended)
                      </div>
                      <div className="mt-1 text-sm font-medium">
                        <MathText text="Every quadratic $ax^2 + bx + c$ can be written in completed square form $a(x + p)^2 + q$, where the turning point is $(-p, q)$." />
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-2 text-slate-900">
                        <div className="font-mono text-xs font-bold text-blue-700">SYMPY-VERIFIED WORKED EXAMPLE</div>
                        <div className="text-sm font-bold">
                          <MathText text="Solve $2x^2 - 5x - 3 = 0$ by factorisation." />
                        </div>
                        <ol className="space-y-1.5 text-xs pl-4 list-decimal">
                          <li>
                            <MathText text="Find two numbers with product $2 \\times (-3) = -6$ and sum $-5$: those are $-6$ and $+1$." />
                          </li>
                          <li>
                            <MathText text="Split the middle term: $2x^2 - 6x + x - 3 = 0 \\Rightarrow 2x(x - 3) + 1(x - 3) = 0$." />
                          </li>
                          <li>
                            <MathText text="Factorise: $(2x + 1)(x - 3) = 0 \\Rightarrow x = -\\frac{1}{2}$ or $x = 3$." />
                          </li>
                        </ol>
                      </div>

                      <div className="rounded-xl border border-emerald-300 bg-emerald-50/70 p-4 space-y-2 text-emerald-950">
                        <div className="font-mono text-xs font-bold text-emerald-800">IIT FOUNDATION BRIDGE SHORTCUT</div>
                        <div className="text-sm font-bold">Vieta&apos;s Root Relationships</div>
                        <p className="text-xs leading-relaxed">
                          <MathText text="For $ax^2 + bx + c = 0$ with roots $\\alpha, \\beta$: Sum $\\alpha + \\beta = -\\frac{b}{a}$ and Product $\\alpha\\beta = \\frac{c}{a}$. Use this to verify your Paper 2 roots in 3 seconds!" />
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* =====================================================================
                SCREEN 3: SAVEMYEXAMS × ALLEN TOPIC QUESTIONS WORKSHEET (#easy-2)
               ===================================================================== */}
            {screen === "questions" && (
              <div className="space-y-5">
                {/* SaveMyExams Top Header + Difficulty Bar */}
                <div className={`rounded-2xl border ${theme.borderCard} ${theme.bgCard} p-5 space-y-4`}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 text-xs font-bold text-blue-600">
                        <span>{currentTopic.subjectTitle}</span>
                        <span>·</span>
                        <span className="font-mono">Topic {currentTopic.topicCode}</span>
                      </div>
                      <h2 className="mt-1 text-xl font-extrabold">{currentTopic.topicTitle}: Topic Questions</h2>
                    </div>

                    {/* Easy / Medium / Hard Segmented Pill Bar */}
                    <div className="inline-flex rounded-xl bg-slate-100 p-1 text-xs">
                      {(["easy", "medium", "hard"] as const).map((tier) => {
                        const active = difficulty === tier;
                        const dot =
                          tier === "easy" ? "bg-emerald-500" : tier === "medium" ? "bg-amber-500" : "bg-rose-500";
                        return (
                          <button
                            key={tier}
                            type="button"
                            onClick={() => {
                              setDifficulty(tier);
                              setQIndex(0);
                              setShowHelp(false);
                              setShowAnswer(false);
                              setShowMarker(false);
                            }}
                            className={`flex items-center gap-2 rounded-lg px-4 py-1.5 font-bold capitalize transition cursor-pointer ${
                              active ? "bg-white text-slate-950 shadow-2xs" : "text-slate-600 hover:text-slate-900"
                            }`}
                          >
                            <span className={`h-2 w-2 rounded-full ${dot}`} />
                            <span>{tier}</span>
                            <span className="font-mono text-[10px] text-slate-400">
                              ({currentTopic[tier].length})
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Numbered Question Jump Pills (#easy-1, #easy-2...) */}
                  <div className="flex items-center justify-between border-t border-slate-200/70 pt-3">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-400 mr-1">Questions:</span>
                      {questionList.map((q, idx) => {
                        const active = qIndex === idx;
                        const done = selfScored[`${subject}-${difficulty}-${idx}`] !== undefined;
                        return (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => {
                              setQIndex(idx);
                              setShowHelp(false);
                              setShowAnswer(false);
                              setShowMarker(false);
                            }}
                            className={`flex h-8 min-w-8 items-center justify-center rounded-lg border px-2.5 font-mono text-xs font-bold transition cursor-pointer ${
                              active
                                ? "border-blue-600 bg-blue-600 text-white"
                                : done
                                ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                                : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                            }`}
                          >
                            {idx + 1}
                            {done && !active && <span className="ml-1 text-[10px]">✓</span>}
                          </button>
                        );
                      })}
                    </div>
                    <span className="font-mono text-xs text-slate-400">
                      Anchor: <strong className="text-blue-600">#{difficulty}-{qIndex + 1}</strong>
                    </span>
                  </div>
                </div>

                {/* SaveMyExams Question Card */}
                {activeQuestion && (
                  <div className={`overflow-hidden rounded-2xl border-2 border-blue-500/40 ${theme.bgCard} shadow-md`}>
                    {/* Card Header */}
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-900 px-5 py-3 text-white">
                      <div className="flex flex-wrap items-center gap-2.5">
                        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600 font-mono text-xs font-extrabold">
                          {qIndex + 1}
                        </span>
                        <span className="rounded-md bg-white/10 px-2.5 py-0.5 text-xs font-semibold text-blue-200">
                          {activeQuestion.tier}
                        </span>
                        <span className="rounded-md bg-emerald-500/20 border border-emerald-400/30 px-2.5 py-0.5 font-mono text-xs font-bold uppercase text-emerald-300">
                          {activeQuestion.command}
                        </span>
                        <span className="font-mono text-xs text-slate-400">{activeQuestion.paper}</span>
                      </div>
                      <span className="rounded-lg bg-white/10 px-3 py-1 font-mono text-xs font-bold text-white">
                        {activeQuestion.marks} marks
                      </span>
                    </div>

                    {/* Question Stem */}
                    <div className="p-6 space-y-4">
                      {activeQuestion.context && (
                        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs md:text-sm text-slate-700 leading-relaxed">
                          <div className="mb-1 font-mono text-[10px] font-bold uppercase text-slate-400">
                            Source Stimulus
                          </div>
                          <MathText text={activeQuestion.context} />
                        </div>
                      )}

                      <div className="flex items-start justify-between gap-4">
                        <div className="text-base md:text-lg font-semibold leading-relaxed">
                          <MathText text={activeQuestion.stem} />
                        </div>
                        <span className="font-mono text-xs font-bold text-slate-400">
                          [{activeQuestion.marks}]
                        </span>
                      </div>

                      {/* Interactive Marker Drawer */}
                      {showMarker && (
                        <div className="rounded-2xl border-2 border-blue-200 bg-blue-50/40 p-4 space-y-3 text-slate-900">
                          <div className="text-xs font-extrabold uppercase tracking-wider text-blue-900">
                            ✍️ Interactive Cambridge Answer Workspace
                          </div>
                          <textarea
                            rows={3}
                            value={draftAnswer}
                            onChange={(e) => setDraftAnswer(e.target.value)}
                            placeholder="Type your working or sociological points here..."
                            className="w-full rounded-xl border border-blue-200 bg-white p-3 text-sm text-slate-900 focus:border-blue-600 focus:outline-none"
                          />
                          <div className="flex flex-wrap items-center gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                setSelfScored((prev) => ({ ...prev, [scoreKey]: activeQuestion.marks }));
                                setShowAnswer(true);
                              }}
                              className="rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white hover:bg-emerald-700 cursor-pointer"
                            >
                              ✓ Submit & Reveal Full Marks ({activeQuestion.marks}/{activeQuestion.marks})
                            </button>
                          </div>
                        </div>
                      )}

                      {/* Question Help Drawer */}
                      {showHelp && (
                        <div className="rounded-2xl border border-indigo-200 bg-indigo-50/70 p-4 space-y-2 text-indigo-950">
                          <div className="text-xs font-extrabold uppercase tracking-wider text-indigo-900">
                            💡 Cambridge Examiner Coaching & Method Guide
                          </div>
                          <ul className="space-y-1.5 pl-4 list-disc text-xs md:text-sm">
                            {activeQuestion.help.map((h, i) => (
                              <li key={i}>
                                <MathText text={h} />
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* View Answer Drawer */}
                      {showAnswer && (
                        <div className="rounded-2xl border border-emerald-300 bg-emerald-50/70 p-4 space-y-2 text-emerald-950">
                          <div className="text-xs font-extrabold uppercase tracking-wider text-emerald-900">
                            👁️ Official Mark Scheme Breakdown ({activeQuestion.marks} marks)
                          </div>
                          <ul className="space-y-1.5 pl-4 list-disc text-xs md:text-sm">
                            {activeQuestion.answer.map((a, i) => (
                              <li key={i}>
                                <MathText text={a} />
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>

                    {/* SaveMyExams Signature Action Bar */}
                    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 bg-slate-50 px-5 py-3.5 text-slate-800">
                      <div className="flex items-center gap-2 text-xs font-bold">
                        <span>How did you do?</span>
                        <span className="rounded-full border border-emerald-300 bg-emerald-100 px-3 py-0.5 font-mono text-emerald-900">
                          {selfScored[scoreKey] ?? "?"} / {activeQuestion.marks} marks
                        </span>
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          onClick={() => setShowMarker(!showMarker)}
                          className="rounded-xl bg-blue-600 hover:bg-blue-700 px-4 py-2 text-xs font-bold text-white cursor-pointer"
                        >
                          ✨ {showMarker ? "Hide marker" : "Mark my answer"}
                        </button>
                        <button
                          type="button"
                          onClick={() => setShowHelp(!showHelp)}
                          className="rounded-xl border border-slate-300 bg-white hover:bg-slate-100 px-3.5 py-2 text-xs font-bold text-slate-800 cursor-pointer"
                        >
                          💡 Question help
                        </button>
                        <button
                          type="button"
                          onClick={() => setShowAnswer(!showAnswer)}
                          className="rounded-xl border border-slate-300 bg-white hover:bg-slate-100 px-3.5 py-2 text-xs font-bold text-slate-800 cursor-pointer"
                        >
                          👁️ {showAnswer ? "Hide answer" : "View answer"}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* =====================================================================
                SCREEN 4: BHANZU 60-SECOND SPRINT GYM & ALLEN IIT TRACKER
               ===================================================================== */}
            {screen === "sprint" && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Left: Bhanzu-Inspired 60-Second Rapid Concept Gym */}
                <div className={`rounded-3xl border ${theme.borderCard} ${theme.bgCard} p-6 space-y-5 shadow-md`}>
                  <div className="flex items-center justify-between">
                    <span className="rounded-lg bg-violet-100 border border-violet-200 px-2.5 py-1 font-mono text-xs font-bold text-violet-800">
                      ⚡ BHANZU BRAIN GYM · 60s SPRINT
                    </span>
                    <span className="font-mono text-xs font-bold text-emerald-600">
                      Score: {sprintScore}00 XP
                    </span>
                  </div>

                  <div className="space-y-2">
                    <div className="text-xs font-bold text-slate-400">
                      {SPRINT_DRILLS[sprintStep].tag}
                    </div>
                    <div className="text-lg font-extrabold leading-relaxed">
                      <MathText text={SPRINT_DRILLS[sprintStep].q} />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    {SPRINT_DRILLS[sprintStep].options.map((opt, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => {
                          if (idx === SPRINT_DRILLS[sprintStep].correct) {
                            setSprintScore((s) => s + 1);
                          }
                          setSprintStep((s) => (s + 1) % SPRINT_DRILLS.length);
                        }}
                        className="rounded-2xl border-2 border-slate-200 bg-slate-50 hover:border-blue-500 hover:bg-blue-50 p-4 text-center text-sm font-bold text-slate-900 transition cursor-pointer"
                      >
                        <MathText text={opt} />
                      </button>
                    ))}
                  </div>
                </div>

                {/* Right: ALLEN Overseas Test & Analytics Matrix */}
                <div className={`rounded-3xl border ${theme.borderCard} ${theme.bgCard} p-6 space-y-4 shadow-md`}>
                  <div className="flex items-center justify-between">
                    <span className="rounded-lg bg-blue-100 border border-blue-200 px-2.5 py-1 font-mono text-xs font-bold text-blue-800">
                      🏛️ ALLEN OVERSEAS ANALYTICS
                    </span>
                    <span className="font-mono text-xs text-slate-400">Topic Accuracy Matrix</span>
                  </div>
                  <h3 className="text-lg font-extrabold">Speed vs. Accuracy Diagnostic</h3>
                  <div className="space-y-3 text-xs">
                    {[
                      { name: "Sociology 0495 · Short Answer (1–4m)", acc: 92, speed: "0.8 min/mark" },
                      { name: "Sociology 0495 · 14-Mark Evaluation Essays", acc: 76, speed: "1.3 min/mark" },
                      { name: "Maths 0580 · Paper 2 Algebraic Manipulation", acc: 88, speed: "0.9 min/mark" },
                      { name: "Maths 0580 · Paper 4 Multi-Step Word Problems", acc: 74, speed: "1.4 min/mark" },
                    ].map((row, idx) => (
                      <div key={idx} className="space-y-1">
                        <div className="flex justify-between font-bold">
                          <span>{row.name}</span>
                          <span className="font-mono text-emerald-600">
                            {row.acc}% · {row.speed}
                          </span>
                        </div>
                        <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-blue-600 to-emerald-500"
                            style={{ width: `${row.acc}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
