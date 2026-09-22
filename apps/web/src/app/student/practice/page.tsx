"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AnswerBox } from "@/components/AnswerBox";
import { useMe } from "@/components/AppShell";
import { MathText } from "@/components/MathText";
import { OralDefenseViva } from "@/components/OralDefenseViva";

const VIVA_ENABLED = false;
import { Button, Card, Empty, ErrorNote } from "@/components/ui";
import { api, type Question } from "@/lib/api";

type SessionOut = { id: string; state: { phase: string; help_level: number; needs_similar_question: boolean } };
type NextItem = { session: SessionOut; question: Question | null; notice: string | null };
type Turn = { kind: string; reply: { content: string; assistance_level: number }; check_question: string | null };

export default function Practice() {
  const me = useMe();
  const subjects = me?.student?.enrollments ?? [];
  const params = useSearchParams();
  const [subjectId, setSubjectId] = useState<string>(params.get("subject") ?? "");
  const [practiceMode, setPracticeMode] = useState<"standard" | "viva">("standard");
  const [session, setSession] = useState<SessionOut | null>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [help, setHelp] = useState<Turn[]>([]);
  const [helpText, setHelpText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [answeredKey, setAnsweredKey] = useState(0);
  const [struggleSeconds, setStruggleSeconds] = useState(45);

  useEffect(() => {
    setStruggleSeconds(45);
    const interval = setInterval(() => {
      setStruggleSeconds((s) => (s > 0 ? s - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [answeredKey]);


  async function run<T>(fn: () => Promise<T>) {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function start() {
    await run(async () => {
      const created = await api<SessionOut>("/tutor/sessions", { method: "POST", json: { subject_id: subjectId, mode: "practice" } });
      setSession(created);
      await next(created.id);
    });
  }

  async function next(id = session?.id) {
    if (!id) return;
    await run(async () => {
      const out = await api<NextItem>(`/tutor/sessions/${id}/next`, { method: "POST" });
      setSession(out.session);
      setQuestion(out.question);
      setNotice(out.notice);
      setHelp([]);
      setAnsweredKey((k) => k + 1);
    });
  }

  async function askHelp() {
    if (!session) return;
    await run(async () => {
      const turn = await api<Turn>(`/tutor/sessions/${session.id}/help`, { method: "POST", json: { message: helpText || null } });
      setHelp((h) => [...h, turn]);
      setHelpText("");
    });
  }

  async function end() {
    if (!session) return;
    await run(async () => {
      await api(`/tutor/sessions/${session.id}/end`, { method: "POST" });
      setSession(null);
      setQuestion(null);
      setHelp([]);
    });
  }

  if (!session) {
    return (
      <div className="space-y-6">
        <div className="rounded-3xl border-2 border-orange-200 bg-gradient-to-br from-amber-50 via-[#FFF4E8] to-orange-50 p-6 md:p-8 shadow-sm">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="space-y-1 text-center md:text-left">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-100 text-orange-800 text-xs font-fun font-bold border border-orange-200">
                <span>🎯</span> Cambridge Practice Lab
              </span>
              <h1 className="text-2xl md:text-3xl font-fun font-bold text-slate-900 tracking-tight">
                Practice Lab & Question Bank 📐
              </h1>
              <p className="text-xs md:text-sm text-slate-600 font-medium max-w-xl">
                Questions are selected from your verified question bank and matched to your current learning needs.
                SymPy automatic checking ensures 100% correct answers.
              </p>
            </div>
            <div className="h-20 w-20 rounded-3xl bg-gradient-to-tr from-amber-400 to-orange-500 flex items-center justify-center text-4xl text-white shadow-md shadow-orange-500/20 select-none animate-float">
              🧩
            </div>
          </div>
        </div>

        <Card title="Start your practice session" subtitle="Choose a subject to begin step-by-step questions">
          {subjects.length === 0 ? (
            <Empty>No subjects enrolled yet. Check back once subjects are set up.</Empty>
          ) : (
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <select
                value={subjectId}
                onChange={(e) => setSubjectId(e.target.value)}
                className="h-11 rounded-2xl border-2 border-amber-200 bg-white px-4 text-sm font-semibold text-slate-800 outline-none focus:border-orange-400"
              >
                <option value="">Choose a subject to practice…</option>
                {subjects.map((s) => (
                  <option key={s.subject_id} value={s.subject_id}>
                    {s.subject_name}
                  </option>
                ))}
              </select>
              <Button disabled={!subjectId || busy} onClick={start}>
                {busy ? "Starting session…" : "Enter Practice Lab →"}
              </Button>
            </div>
          )}
          {error ? <ErrorNote error={error} /> : null}
        </Card>
      </div>
    );
  }

  const currentSubject = subjects.find((s) => s.subject_id === subjectId)?.subject_name ?? "Cambridge Subject";
  const helpLevel = session.state.help_level;

  return (
    <div className="space-y-5">
      {/* Friendly Header Banner from Reference Design */}
      <div className="bg-white border-2 border-orange-200 rounded-3xl p-5 shadow-sm flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={end}
            title="Leave session"
            className="h-11 w-11 rounded-2xl bg-orange-50 border border-orange-200 text-orange-600 flex items-center justify-center hover:bg-orange-100 font-bold transition-all hover:scale-105 cursor-pointer"
          >
            ←
          </button>
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full bg-orange-100 text-orange-700 text-xs font-fun font-bold border border-orange-200">
                {currentSubject}
              </span>
              <span className="text-xs text-slate-400 font-medium">
                {question ? `${question.marks} Marks` : "Active Question"}
              </span>
            </div>
            <h2 className="text-lg font-fun font-bold text-slate-900 mt-0.5">
              Interactive Practice Playground 🧩
            </h2>
          </div>
        </div>

        {/* Mode Switcher */}
        <div className="flex items-center gap-1.5 bg-slate-100 p-1.5 rounded-2xl border border-slate-200">
          <button
            type="button"
            onClick={() => setPracticeMode("standard")}
            className={`px-3 py-1.5 rounded-xl text-xs font-fun font-bold transition-all ${
              practiceMode === "standard"
                ? "bg-white text-orange-600 shadow-xs border border-orange-200"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            📐 Standard Lab
          </button>
          {/* Hidden 22 Sep 2026: the Viva's replies were scripted (any answer was praised) and it sent her voice to
              the browser's speech service. It returns once rebuilt on the grounded Tutor (review of 22 Sep). */}
          {VIVA_ENABLED && <button
            type="button"
            onClick={() => setPracticeMode("viva")}
            className={`px-3 py-1.5 rounded-xl text-xs font-fun font-bold transition-all ${
              practiceMode === "viva"
                ? "bg-purple-600 text-white shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            🎓 Oral Defense (Blackboard Viva)
          </button>}
        </div>

        {/* Socratic Encouraging Meter */}
        <div className="flex items-center gap-3 bg-amber-50 px-4 py-2 rounded-2xl border border-amber-200">
          <span className="text-2xl select-none">🪄</span>
          <div>
            <div className="text-[10.5px] uppercase tracking-wider font-fun font-bold text-amber-800">
              Support Mode: Socratic Coach
            </div>
            <div className="text-xs font-bold text-slate-800">
              {helpLevel === 0
                ? "You're solving this completely on your own! (L0)"
                : `Active guidance level L${helpLevel}`}
            </div>
          </div>
        </div>
      </div>

      {VIVA_ENABLED && practiceMode === "viva" ? (
        <OralDefenseViva />
      ) : (
      <div className="grid gap-6 xl:grid-cols-12">
        {/* Left 7 cols: Question & Solver Canvas */}
        <div className="xl:col-span-7 space-y-4">
          <Card
            title="Step-by-Step Solver Playground"
            subtitle="SymPy automatic verification is active"
          >
            {notice && (
              <p className="rounded-2xl bg-orange-50 border border-orange-200 px-4 py-2.5 text-sm text-orange-800 font-medium">
                {notice}
              </p>
            )}
            {session.state.needs_similar_question && (
              <div className="rounded-2xl bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900 font-medium flex items-center gap-2">
                <span>🔄</span>
                <span>Next up: a twin question to lock in what you just learned.</span>
              </div>
            )}

            {question ? (
              <AnswerBox key={answeredKey} question={question} sessionId={session.id} />
            ) : (
              <Empty>No question available right now.</Empty>
            )}

            <div className="flex flex-wrap items-center gap-3 pt-3 border-t border-slate-100">
              <Button variant="secondary" disabled={busy} onClick={() => next()}>
                Next question →
              </Button>
              <Button variant="ghost" disabled={busy} onClick={end}>
                Finish session
              </Button>
            </div>
            {error ? <ErrorNote error={error} /> : null}
          </Card>
        </div>

        {/* Right 5 cols: Mascot Socratic AI Buddy */}
        <div className="xl:col-span-5 space-y-4">
          <div className="bg-white rounded-3xl border-2 border-amber-200 p-5 shadow-sm space-y-4">
            {/* Mascot Header */}
            <div className="flex items-center gap-3 pb-3 border-b border-slate-100">
              <div className="h-12 w-12 rounded-2xl bg-amber-100 border border-amber-300 flex items-center justify-center text-3xl shadow-xs select-none">
                🦉
              </div>
              <div>
                <h4 className="font-fun font-bold text-slate-900">Scholr AI Study Buddy</h4>
                <p className="text-xs text-slate-500 font-medium">I never give away answers, but I give awesome clues!</p>
              </div>
            </div>

            {/* Conversation Clues Stream */}
            <div className="space-y-3 text-xs leading-relaxed max-h-[380px] overflow-y-auto pr-1">
              {help.length === 0 && (
                <div className="bg-amber-50/80 border border-amber-200 rounded-2xl p-4 text-slate-700 space-y-1">
                  <span className="font-fun font-bold text-orange-700 block text-sm">
                    Ready when you are! 🌟
                  </span>
                  <p>
                    Read the question carefully. If you get stuck at any step, ask me for a hint and I&apos;ll give you a gentle nudge!
                  </p>
                </div>
              )}

              {help.map((turn, i) => (
                <div key={i} className="space-y-2">
                  <div className="bg-amber-50 border border-amber-200 rounded-2xl rounded-tl-none p-3.5 text-slate-800 shadow-2xs">
                    <span className="font-fun font-bold text-orange-600 block mb-1">
                      {turn.kind === "ask_for_attempt" ? "💡 First Step Nudge:" : `Hint Level ${turn.reply.assistance_level}:`}
                    </span>
                    <MathText text={turn.reply.content} />
                    {turn.check_question && (
                      <div className="mt-2 bg-white p-2.5 rounded-xl border border-amber-200 font-medium text-slate-900">
                        <MathText text={turn.check_question} />
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Hint Request Form with Productive Struggle */}
            <div className="pt-2 border-t border-slate-100 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-fun font-bold text-slate-500 uppercase tracking-wider block">
                  Need a little boost?
                </span>
                {struggleSeconds > 0 && (
                  <span className="text-[10.5px] font-fun font-bold text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full animate-pulse">
                    ⏳ Struggle Window: {struggleSeconds}s
                  </span>
                )}
              </div>
              <textarea
                value={helpText}
                onChange={(e) => setHelpText(e.target.value)}
                rows={2}
                className="w-full rounded-2xl border-2 border-amber-200 bg-white p-3 text-xs font-normal outline-none focus:border-orange-400"
                placeholder="What have you tried so far? (optional)"
              />
              <div className="flex flex-col gap-1.5">
                <Button
                  disabled={busy || !question || struggleSeconds > 0}
                  onClick={askHelp}
                  className="w-full"
                >
                  {busy
                    ? "Thinking of a clue…"
                    : struggleSeconds > 0
                    ? `⏳ Productive Struggle: Think first (${struggleSeconds}s)`
                    : "💡 Ask the Tutor for a hint"}
                </Button>
                {struggleSeconds > 0 && (
                  <button
                    type="button"
                    onClick={() => setStruggleSeconds(0)}
                    className="text-[11px] text-slate-400 hover:text-slate-600 underline text-center cursor-pointer transition-colors"
                  >
                    I&apos;ve already spent time thinking, show hint now
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Encouragement Card */}
          <div className="bg-gradient-to-r from-purple-100 to-indigo-100 rounded-3xl border border-purple-200 p-4 flex items-center gap-3 shadow-2xs">
            <div className="text-3xl select-none">🏅</div>
            <div className="text-xs text-purple-900 font-medium">
              <strong className="block font-fun font-bold text-sm text-purple-950">
                Cambridge Mastery Goal!
              </strong>
              Solving questions without revealing hints helps secure topics and raises your independent score.
            </div>
          </div>
        </div>
      </div>
      )}
    </div>
  );
}
