"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";

type Choice = { subject_id: string; subject_name: string; objective_id: string | null; objective_code: string | null; label: string };
type Route = {
  source: string;
  intent: string;
  subject_id: string | null;
  objective_id: string | null;
  choices: Choice[];
  assessment_id: string | null;
};

// Top-bar "Ask" box: the Master Router decides where the question goes (ARCHITECTURE §7).
export function AskBox() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [choices, setChoices] = useState<Choice[]>([]);
  const [busy, setBusy] = useState(false);

  function go(route: { intent: string; subject_id: string | null; objective_id?: string | null; assessment_id?: string | null }, message: string) {
    const params = new URLSearchParams({ q: message });
    if (route.subject_id) params.set("subject", route.subject_id);
    if (route.objective_id) params.set("objective", route.objective_id);
    const target =
      route.assessment_id ? `/student/tests/${route.assessment_id}`
      : route.intent === "practice" || route.intent === "help_on_attempt" || route.intent === "check_answer" ? `/student/practice?${params}`
      : route.intent === "plan" ? "/student"
      : route.intent === "progress" ? "/student/progress"
      : `/student/tutor?${params}`;
    setChoices([]);
    setText("");
    router.push(target);
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const message = text.trim();
    if (!message) return;
    setBusy(true);
    try {
      const route = await api<Route>("/route", { method: "POST", json: { message } });
      if (route.source === "ask" || (route.choices.length > 0 && !route.objective_id && route.source !== "session")) {
        setChoices(route.choices);
      } else {
        go(route, message);
      }
    } catch {
      go({ intent: "explain", subject_id: null }, message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative w-full max-w-xl">
      <form onSubmit={submit} className="flex h-10 items-center gap-2 rounded-full border border-line bg-white pl-4 pr-1 shadow-sm">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={2000}
          aria-label="Ask a question"
          placeholder="Ask a question, get help, or practise a topic…"
          className="min-w-0 flex-1 bg-transparent text-sm outline-none"
        />
        <button disabled={busy || !text.trim()} className="h-8 rounded-full bg-[#4450ee] px-4 text-xs font-semibold text-white disabled:opacity-50">
          {busy ? "…" : "Ask"}
        </button>
      </form>
      {choices.length > 0 && (
        <div className="absolute left-0 right-0 top-12 z-20 flex flex-col gap-1 rounded-xl border border-line bg-white p-2 shadow-lg">
          <p className="px-2 py-1 text-xs text-muted">Which one did you mean?</p>
          {choices.map((c) => (
            <button
              key={`${c.subject_id}${c.objective_id ?? ""}`}
              onClick={() => go({ intent: "explain", subject_id: c.subject_id, objective_id: c.objective_id }, text)}
              className="rounded-lg px-2 py-2 text-left text-sm hover:bg-tile"
            >
              {c.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
