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
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-orange-200 bg-orange-50/70 px-4 py-2.5 text-sm">
          <span className="font-medium text-slate-700">
            Asking about <b className="text-slate-900">{scope.data.code} {scope.data.statement}</b>
          </span>
          <Link href={`/student/learn/topic/${objectiveId}`} className="text-xs font-fun font-bold text-orange-600 hover:underline">
            ← Back to the topic
          </Link>
        </div>
      )}
      {/* Friendly Tutor Header */}
      <div className="rounded-3xl border-2 border-amber-200 bg-gradient-to-br from-amber-50 via-[#FFF4E8] to-orange-50 p-6 md:p-7 shadow-sm">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="h-14 w-14 rounded-3xl bg-amber-100 border-2 border-amber-300 flex items-center justify-center text-4xl shadow-sm select-none animate-float">
              🦉
            </div>
            <div>
              <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-orange-100 text-orange-800 text-[11px] font-fun font-bold border border-orange-200 mb-1">
                <span>🪄</span> Socratic Study Buddy
              </div>
              <h1 className="text-xl md:text-2xl font-fun font-bold text-slate-900">
                Scholr Tutor
              </h1>
              <p className="text-xs text-slate-500 font-medium">
                Grounded directly in your official Cambridge textbooks. I explain step-by-step!
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5 w-full sm:w-auto">
            <select
              value={subjectId}
              disabled={Boolean(sessionId)}
              onChange={(e) => setSubjectId(e.target.value)}
              className="h-11 flex-1 sm:flex-none rounded-2xl border-2 border-amber-200 bg-white px-4 text-xs font-bold text-slate-800 outline-none focus:border-orange-400"
            >
              <option value="">Choose a subject…</option>
              {subjects.map((s) => (
                <option key={s.subject_id} value={s.subject_id}>
                  {s.subject_name}
                </option>
              ))}
            </select>
            {sessionId && (
              <Button variant="secondary" onClick={end}>
                New chat ↺
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Chat Stream Card */}
      <div className="rounded-3xl border-2 border-amber-200/80 bg-white p-5 md:p-6 shadow-sm flex flex-col gap-4 min-h-[480px]">
        <div className="flex-1 flex flex-col gap-4 overflow-y-auto pr-1">
          {log.length === 0 && (
            <div className="my-auto py-8 text-center space-y-3 max-w-md mx-auto">
              <span className="text-5xl inline-block select-none animate-bounce">🦉</span>
              <h3 className="text-base font-fun font-bold text-slate-800">
                What are we exploring today?
              </h3>
              <p className="text-xs text-slate-500 font-medium leading-relaxed">
                Ask about any concept, equation, or exam skill. I will use your coursebooks to explain without just giving away answers!
              </p>
              {subjectId && (
                <div className="pt-2 flex flex-wrap justify-center gap-2">
                  {[
                    "How do I complete the square?",
                    "What makes snowball sampling non-representative?",
                    "Can you give me an easy example of indices?",
                  ].map((sample) => (
                    <button
                      key={sample}
                      type="button"
                      onClick={() => setText(sample)}
                      className="text-xs font-semibold text-orange-700 bg-orange-50 hover:bg-orange-100 border border-orange-200 rounded-xl px-3 py-1.5 transition-all hover:scale-102 cursor-pointer"
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
                className="self-end max-w-[85%] rounded-3xl rounded-tr-xs bg-gradient-to-r from-orange-500 to-amber-500 px-4 py-3 text-sm font-medium text-white shadow-md shadow-orange-500/20"
              >
                {entry.text}
              </div>
            ) : (
              <div
                key={i}
                className="self-start max-w-[90%] rounded-3xl rounded-tl-xs border-2 border-amber-200 bg-[#FFFDF9] p-4 md:p-5 text-sm text-slate-900 shadow-2xs space-y-2.5"
              >
                <div className="flex items-center gap-2 pb-2 border-b border-amber-100">
                  <span className="text-lg">🦉</span>
                  <span className="text-xs font-fun font-bold text-orange-600">
                    Scholr Tutor
                  </span>
                </div>

                <div className="leading-relaxed">
                  <MathText text={entry.text} />
                </div>

                {entry.turn?.check_question && (
                  <div className="mt-2 rounded-2xl bg-amber-50 border border-amber-200 p-3 text-xs font-medium text-slate-800">
                    <span className="font-fun font-bold text-orange-700 block mb-1">
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
                      className="bg-amber-50 text-amber-900 border border-amber-200 px-2.5 py-0.5 rounded-full"
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
            <div className="self-start flex items-center gap-2 bg-amber-50 border border-amber-200 px-4 py-2.5 rounded-2xl text-xs text-amber-900 font-medium animate-pulse">
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
            className="h-12 min-w-0 flex-1 rounded-2xl border-2 border-amber-200 bg-white px-4 text-sm font-normal text-slate-900 outline-none focus:border-orange-400 placeholder:text-slate-400"
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
                : "border-amber-200 bg-white text-slate-600 hover:bg-amber-50 hover:text-amber-800"
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
