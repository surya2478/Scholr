"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { MathText } from "@/components/MathText";
import { Button, ErrorNote } from "@/components/ui";
import { api } from "@/lib/api";
import { getToken } from "@/lib/session";
import { tutorHref } from "@/lib/tutor";

// "Explore with AI" on a lesson section (docs/STUDENT-APP.md AC-U15): the Tutor, opened where she is reading
// rather than on another page. It is the same grounded Tutor — retrieval over her own books, citations, the
// copy check and the safety rules — so nothing here asks a model to talk about a topic from general knowledge.

type Citation = { source_title: string; printed_page: number | null; heading_path: string | null };
type Turn = {
  reply: { content: string; retrieval_state: string | null; citations: Citation[] };
};

const GROUNDING: Record<string, string> = {
  HIGH: "From your textbook",
  MEDIUM: "Partly from your textbook",
  LOW: "Limited textbook support",
  NONE: "Not found in your textbook",
};

export function ExploreWithAI({
  subjectId,
  objectiveId,
  heading,
  question,
}: {
  subjectId: string;
  objectiveId: string;
  heading: string;
  question: string;
}) {
  const [open, setOpen] = useState(false);
  const [answer, setAnswer] = useState("");
  const [turn, setTurn] = useState<Turn | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const asked = useRef(false);

  async function ask() {
    setOpen(true);
    if (asked.current) return;
    asked.current = true;
    setBusy(true);
    setError(null);
    try {
      const session = await api<{ id: string }>("/tutor/sessions", {
        method: "POST",
        json: { subject_id: subjectId, objective_id: objectiveId, mode: "learn" },
      });
      const token = getToken();
      const res = await fetch(`/api/tutor/sessions/${session.id}/turns/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ message: question }),
      });
      if (!res.ok || !res.body) throw new Error("The Tutor could not answer just now.");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let streamed = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const parsed = JSON.parse(line.slice(6));
            if (parsed.type === "token") {
              streamed += parsed.content;
              setAnswer(streamed);
            } else if (parsed.type === "done") {
              setTurn(parsed.turn);
              setAnswer(streamed || parsed.turn.reply.content);
            }
          } catch {
            // a partial chunk: the next read completes it
          }
        }
      }
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const state = turn?.reply.retrieval_state ?? null;

  return (
    <>
      <button
        onClick={ask}
        className="self-start rounded-xl border border-violet-200 bg-violet-50 px-2.5 py-1 text-[11px] font-fun font-bold text-violet-700 hover:bg-violet-100"
      >
        ✨ Explore with AI
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-0 sm:items-center sm:p-6"
          onClick={() => setOpen(false)}
        >
          <div
            className="flex max-h-[85vh] w-full max-w-lg flex-col gap-3 overflow-y-auto rounded-t-3xl bg-white p-5 shadow-xl sm:rounded-3xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="font-fun text-lg font-extrabold text-slate-900">{heading}</h2>
                <p className="text-[11px] text-muted">The Tutor, reading your own course books.</p>
              </div>
              <button onClick={() => setOpen(false)} className="text-sm font-bold text-slate-400 hover:text-slate-700">
                ✕
              </button>
            </div>

            {error ? <ErrorNote error={error} /> : null}
            {busy && !answer && <p className="text-sm text-slate-500">Reading your books…</p>}
            {answer && <MathText text={answer} className="text-sm leading-relaxed text-slate-800" />}

            {state && (
              <p className="text-[11px] font-semibold text-slate-500">
                {GROUNDING[state] ?? state}
                {turn?.reply.citations.length
                  ? ` · ${turn.reply.citations
                      .map((c) => `${c.source_title}${c.printed_page ? `, p. ${c.printed_page}` : ""}`)
                      .join(" · ")}`
                  : ""}
              </p>
            )}

            {!busy && (
              <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
                <Link href={tutorHref({ subjectId, objectiveId, about: heading, ask: question })}>
                  <Button variant="secondary" className="h-8 px-3 text-xs">
                    Keep asking in the Tutor
                  </Button>
                </Link>
                <Button variant="ghost" className="h-8 px-3 text-xs" onClick={() => setOpen(false)}>
                  Back to the lesson
                </Button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
