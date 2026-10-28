"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useMe } from "@/components/AppShell";
import { MathText } from "@/components/MathText";
import { Button, Card, ErrorNote } from "@/components/ui";
import { api } from "@/lib/api";
import { getToken } from "@/lib/session";
import { useApi } from "@/lib/useApi";
import { MAX_SECONDS, type Recording, startRecording, toBase64 } from "@/lib/voiceRecorder";

type Citation = { source_title: string; printed_page: number | null; heading_path: string | null };
type Message = { id: string; role: string; content: string; retrieval_state: string | null; citations: Citation[] };
type Turn = { kind: string; reply: Message; check_question: string | null };

const GROUNDING: Record<string, string> = {
  HIGH: "From your textbook",
  MEDIUM: "Partly from your textbook",
  LOW: "Limited textbook support",
  NONE: "Not found in your textbook",
};

export default function Tutor() {
  const me = useMe();
  const params = useSearchParams();
  const subjects = me?.student?.enrollments ?? [];
  const [subjectId, setSubjectId] = useState(params.get("subject") ?? "");
  // Opened from a topic page: the session is about that objective, so retrieval and the lesson match it.
  const objectiveId = params.get("objective");
  const scope = useApi<{ code: string; statement: string }>(objectiveId ? `/objectives/${objectiveId}` : null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [log, setLog] = useState<{ role: "you" | "tutor"; turn?: Turn; text: string }[]>([]);
  const [text, setText] = useState(params.get("q") ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  // Voice input (docs/STUDENT-APP.md §16): recorded here, transcribed by Scholr's API through the gateway, and put
  // in the box for her to check. Not the browser's speech service, which would send her voice to Google/Microsoft.
  const [voice, setVoice] = useState<"idle" | "recording" | "transcribing">("idle");
  const [heardNote, setHeardNote] = useState<string | null>(null);
  const recording = useRef<Recording | null>(null);
  const stopTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!subjectId && subjects.length > 0) {
      setSubjectId(subjects[0].subject_id);
    }
  }, [subjectId, subjects]);

  async function toggleVoice() {
    if (voice === "transcribing") return;
    if (voice === "recording") {
      await finishRecording();
      return;
    }
    setError(null);
    setHeardNote(null);
    try {
      recording.current = await startRecording();
      setVoice("recording");
      stopTimer.current = setTimeout(() => void finishRecording(), MAX_SECONDS * 1000);
    } catch {
      setError(new Error("The microphone isn't available. Check the browser's permission, or type your question."));
    }
  }

  async function finishRecording() {
    if (stopTimer.current) clearTimeout(stopTimer.current);
    const current = recording.current;
    recording.current = null;
    if (!current) return;
    setVoice("transcribing");
    try {
      const wav = await current.stop();
      const heard = await api<{ text: string; unclear: boolean }>("/tutor/speech", {
        method: "POST",
        json: { audio: await toBase64(wav), format: "wav" },
      });
      setText((prev) => (prev ? `${prev} ${heard.text}` : heard.text));
      setHeardNote(
        heard.unclear
          ? "Some words were hard to hear. Check them, then press Send."
          : "Check what I heard, then press Send."
      );
    } catch (err) {
      setError(err);
    } finally {
      setVoice("idle");
    }
  }

  useEffect(() => () => recording.current?.cancel(), []);

  async function send(event: React.FormEvent) {
    event.preventDefault();
    const message = text.trim();
    if (!message || !subjectId) return;
    setBusy(true);
    setError(null);
    setHeardNote(null);
    setLog((l) => [...l, { role: "you", text: message }]);
    setText("");
    try {
      let id = sessionId;
      if (!id) {
        id = (await api<{ id: string }>("/tutor/sessions", { method: "POST", json: { subject_id: subjectId, objective_id: objectiveId, mode: "learn" } })).id;
        setSessionId(id);
      }

      // Add a slot for the incoming tutor message
      setLog((l) => [...l, { role: "tutor", text: "" }]);

      const token = getToken();
      const res = await fetch(`/api/tutor/sessions/${id}/turns/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message }),
      });

      if (res.ok && res.body) {
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let streamedText = "";
        let finalTurn: Turn | undefined = undefined;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const parsed = JSON.parse(line.slice(6));
                if (parsed.type === "token") {
                  streamedText += parsed.content;
                  setLog((l) => {
                    const copy = [...l];
                    const lastIdx = copy.length - 1;
                    if (lastIdx >= 0 && copy[lastIdx].role === "tutor") {
                      copy[lastIdx] = { ...copy[lastIdx], text: streamedText };
                    }
                    return copy;
                  });
                } else if (parsed.type === "done") {
                  finalTurn = parsed.turn;
                  setLog((l) => {
                    const copy = [...l];
                    const lastIdx = copy.length - 1;
                    if (lastIdx >= 0 && copy[lastIdx].role === "tutor") {
                      copy[lastIdx] = { role: "tutor", turn: finalTurn, text: streamedText || finalTurn!.reply.content };
                    }
                    return copy;
                  });
                }
              } catch {
                // ignore chunk parse errors
              }
            }
          }
        }
      } else {
        // Fallback to standard endpoint
        const turn = await api<Turn>(`/tutor/sessions/${id}/turns`, { method: "POST", json: { message } });
        setLog((l) => {
          const copy = [...l];
          const lastIdx = copy.length - 1;
          if (lastIdx >= 0 && copy[lastIdx].role === "tutor") {
            copy[lastIdx] = { role: "tutor", turn, text: turn.reply.content };
          } else {
            copy.push({ role: "tutor", turn, text: turn.reply.content });
          }
          return copy;
        });
      }
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function end() {
    if (sessionId) await api(`/tutor/sessions/${sessionId}/end`, { method: "POST" }).catch(() => undefined);
    setSessionId(null);
    setLog([]);
  }

  return (
    <div className="space-y-5">
      {scope.data && objectiveId && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-blue-200 bg-blue-50/70 px-4 py-2.5 text-sm">
          <span className="font-medium text-slate-700">
            Asking about <b className="text-slate-900">{scope.data.code} {scope.data.statement}</b>
          </span>
          <Link href={`/student/learn/topic/${objectiveId}`} className="text-xs font-fun font-bold text-blue-600 hover:underline">
            ← Back to the topic
          </Link>
        </div>
      )}
      {/* Tutor header */}
      <div className="rounded-2xl border border-slate-800 bg-gradient-to-r from-[#0B1528] via-[#122240] to-[#1E3A8A] p-6 md:p-7 text-white shadow-md">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="h-13 w-13 rounded-2xl bg-blue-500/20 border border-blue-400/30 flex items-center justify-center text-3xl shadow-xs select-none shrink-0">
              🤖
            </div>
            <div>
              <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-blue-500/20 text-blue-200 text-[10px] font-bold uppercase tracking-wider border border-blue-400/30 mb-1">
                <span>⚡</span> Grounded in your own textbooks
              </div>
              <h1 className="text-xl md:text-2xl font-extrabold tracking-tight text-white">
                Tutor
              </h1>
              <p className="text-xs text-slate-300 font-medium">
                Grounded in your official Cambridge IGCSE coursebooks with step-by-step guidance and citations.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5 w-full sm:w-auto">
            <select
              value={subjectId}
              disabled={Boolean(sessionId)}
              onChange={(e) => setSubjectId(e.target.value)}
              className="h-10 flex-1 sm:flex-none rounded-xl border border-white/20 bg-white/10 px-3.5 text-xs font-bold text-white outline-none focus:border-blue-400"
            >
              <option value="" className="text-slate-900">Choose a subject…</option>
              {subjects.map((s) => (
                <option key={s.subject_id} value={s.subject_id} className="text-slate-900">
                  {s.subject_name}
                </option>
              ))}
            </select>
            {sessionId && (
              <Button variant="secondary" onClick={end}>
                New session ↺
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Chat Stream Card */}
      <div className="rounded-2xl border border-slate-200/90 bg-white p-5 md:p-6 shadow-xs flex flex-col gap-4 min-h-[480px]">
        <div className="flex-1 flex flex-col gap-4 overflow-y-auto pr-1">
          {log.length === 0 && (
            <div className="my-auto py-8 text-center space-y-4 max-w-xl mx-auto">
              <div className="mx-auto h-12 w-12 rounded-2xl bg-blue-50 border border-blue-200 flex items-center justify-center text-2xl select-none">
                🤖
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-extrabold text-slate-900">
                  What concept, derivation, or exam question are we solving?
                </h3>
                <p className="text-xs text-slate-500 font-medium leading-relaxed">
                  Ask for a structured summary, step-by-step mathematical working, or Cambridge mark-scheme breakdown. Every answer cites the exact textbook page.
                </p>
              </div>
              {subjectId && (
                <div className="pt-2 flex flex-wrap justify-center gap-2">
                  {[
                    "Summarise the key definitions and examiner traps for this topic in 5 bullet points.",
                    "Walk me through completing the square step-by-step and explain how to find the turning point.",
                    "What makes snowball sampling non-representative in Sociology Paper 1?",
                    "Give me a medium-to-hard 4-mark exam question on this topic and test my working.",
                  ].map((sample) => (
                    <button
                      key={sample}
                      type="button"
                      onClick={() => setText(sample)}
                      className="text-xs font-semibold text-blue-800 bg-blue-50/80 hover:bg-blue-100/80 border border-blue-200 rounded-xl px-3.5 py-2 transition-all cursor-pointer text-left"
                    >
                      “{sample}”
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {log.map((entry, i) =>
            entry.role === "you" ? (
              <div
                key={i}
                className="self-end max-w-[85%] rounded-3xl rounded-tr-xs bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-3 text-sm font-medium text-white shadow-md shadow-blue-600/20"
              >
                {entry.text}
              </div>
            ) : (
              <div
                key={i}
                className="self-start max-w-[90%] rounded-3xl rounded-tl-xs border-2 border-slate-200 bg-white p-4 md:p-5 text-sm text-slate-900 shadow-2xs space-y-2.5"
              >
                <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
                  <span className="text-lg">🦉</span>
                  <span className="text-xs font-fun font-bold text-blue-600">
                    Scholr Tutor
                  </span>
                </div>

                <div className="leading-relaxed">
                  <MathText text={entry.text} />
                </div>

                {entry.turn?.check_question && (
                  <div className="mt-2 rounded-2xl bg-amber-50 border border-slate-200 p-3 text-xs font-medium text-slate-800">
                    <span className="font-fun font-bold text-blue-700 block mb-1">
                      Check your understanding:
                    </span>
                    <MathText text={entry.turn.check_question} />
                  </div>
                )}

                {/* Grounding & Citations */}
                <div className="mt-2 flex flex-wrap items-center gap-2 pt-2 border-t border-slate-100 text-[11px] text-slate-500 font-medium">
                  {entry.turn?.reply.retrieval_state && (
                    <span className="bg-emerald-50 text-emerald-800 border border-emerald-200 px-2.5 py-0.5 rounded-full font-bold">
                      {GROUNDING[entry.turn.reply.retrieval_state] ?? entry.turn.reply.retrieval_state}
                    </span>
                  )}
                  {entry.turn?.reply.citations.map((c, j) => (
                    <span
                      key={j}
                      className="bg-amber-50 text-amber-900 border border-slate-200 px-2.5 py-0.5 rounded-full"
                    >
                      📖 {c.source_title}
                      {c.printed_page ? ` p.${c.printed_page}` : ""}
                    </span>
                  ))}
                </div>
              </div>
            ),
          )}

          {busy && (
            <div className="self-start flex items-center gap-2 bg-amber-50 border border-slate-200 px-4 py-2.5 rounded-2xl text-xs text-amber-900 font-medium animate-pulse">
              <span>🦉</span>
              <span>Thinking & checking Cambridge textbooks…</span>
            </div>
          )}
        </div>

        {/* Input Form */}
        <form onSubmit={send} className="flex items-center gap-2.5 pt-3 border-t border-slate-100">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={2000}
            className="h-12 min-w-0 flex-1 rounded-2xl border-2 border-slate-200 bg-white px-4 text-sm font-normal text-slate-900 outline-none focus:border-blue-500 placeholder:text-slate-400"
            placeholder={
              voice === "recording"
                ? "🎙 Recording… tap ■ when you've finished"
                : voice === "transcribing"
                ? "Writing down what you said…"
                : subjectId
                ? "Ask a question about this topic…"
                : "Choose a subject first to unlock study buddy"
            }
          />
          <button
            type="button"
            onClick={() => void toggleVoice()}
            disabled={voice === "transcribing" || !subjectId}
            className={`flex h-12 w-12 items-center justify-center rounded-2xl border-2 transition disabled:opacity-50 ${
              voice === "recording"
                ? "border-rose-400 bg-rose-50 text-rose-600 animate-pulse"
                : "border-slate-200 bg-white text-slate-600 hover:bg-amber-50 hover:text-amber-800"
            }`}
            title={voice === "recording" ? "Stop recording" : "Ask with your voice"}
            aria-label={voice === "recording" ? "Stop recording" : "Ask with your voice"}
          >
            {voice === "recording" ? "■" : voice === "transcribing" ? "…" : "🎙"}
          </button>
          <Button disabled={busy || !subjectId || !text.trim()}>
            Send ↵
          </Button>
        </form>

        {heardNote && <p className="text-[11px] font-semibold text-amber-800">{heardNote}</p>}
        {error ? <ErrorNote error={error} /> : null}
      </div>
    </div>
  );
}
