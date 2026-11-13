"use client";

import Link from "next/link";
import { useState } from "react";
import { api, type Plan, type TimelineBlock } from "@/lib/api";
import { KIND_LABELS, minutes } from "@/lib/format";
import { Chip, Empty } from "./ui";

// My Day as a timeline: fixed commitments at their own times, study blocks in the gaps between them.
// Tile colours follow the kind of work, never the subject (subject behaviour lives in the subject configs).
const TILES: Record<string, string> = {
  commitment: "#e9eefd",
  assessment: "linear-gradient(135deg,#8b5cf6,#5b4fe8)",
  mistake_fix: "linear-gradient(135deg,#fb7185,#e8364f)",
  revision: "linear-gradient(135deg,#5b8def,#3f5fe0)",
  school_topic: "linear-gradient(135deg,#34d399,#10b981)",
  practice: "linear-gradient(135deg,#fbbf24,#f59e0b)",
  challenge: "linear-gradient(135deg,#22d3ee,#0891b2)",
  reinforcement: "linear-gradient(135deg,#a78bfa,#7c6bf0)",
};

const STATUS: Record<
  string,
  { tone: "good" | "brand" | "neutral" | "warn"; label: string }
> = {
  completed: { tone: "good", label: "Completed" },
  in_progress: { tone: "brand", label: "In progress" },
  planned: { tone: "neutral", label: "Not started" },
  skipped: { tone: "warn", label: "Skipped" },
};

function clock(block: TimelineBlock): string {
  if (!block.start) return "Any time";
  return `${block.start.slice(0, 5)} – ${(block.end ?? "").slice(0, 5)}`;
}

export function DayTimeline({
  plan,
  onChange,
  readOnly = false,
}: {
  plan: Plan;
  onChange?: (p: Plan) => void;
  readOnly?: boolean;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [refused, setRefused] = useState<{ id: string; message: string } | null>(null);

  async function update(itemId: string, status: "completed" | "skipped") {
    setBusy(itemId);
    setRefused(null);
    try {
      onChange?.(
        await api<Plan>(`/plan/items/${itemId}`, {
          method: "PATCH",
          json: { status },
        }),
      );
    } catch (err) {
      setRefused({ id: itemId, message: err instanceof Error ? err.message : "That didn't save. Try again." });
    } finally {
      setBusy(null);
    }
  }

  if (plan.timeline.length === 0) return <Empty>Nothing planned today.</Empty>;

  return (
    <ul className="flex flex-col gap-1.5">
      {plan.timeline.map((block, i) => {
        const commitment = block.kind === "commitment";
        // Why this block is here. A reinforcement block names the outside class it came from (AC-X12), and a
        // template line for the rest, so the day always explains itself.
        const item = plan.items.find((x) => x.id === block.plan_item_id);
        const why = item?.reason ?? null;
        // Reading a topic is not finishing it: Done waits until she has answered one of its questions today.
        const answerFirst = item?.needs_answer && item.objective_id ? item.objective_id : null;
        const status = block.status ? STATUS[block.status] : null;
        const open =
          block.status === "planned" || block.status === "in_progress";
        return (
          <li
            key={block.plan_item_id ?? `${block.title}-${i}`}
            className="rounded-xl border border-line-soft bg-[#fbfcfe]"
          >
            <div className="flex flex-wrap items-center gap-y-2 py-2 md:flex-nowrap md:py-0">
              <div className="flex h-full min-w-[118px] items-center border-line-soft pl-4 text-[11.5px] text-ink-2 md:h-[43px] md:border-r">
                {clock(block)}
              </div>
              <div
                className="mx-3.5 flex h-[30px] w-[30px] flex-none items-center justify-center rounded-lg text-[11px] font-bold text-white"
                style={{ background: TILES[block.kind] ?? TILES.practice }}
                aria-hidden
              >
                {commitment
                  ? ""
                  : (KIND_LABELS[block.kind] ?? block.kind).slice(0, 1)}
              </div>
              <div className="min-w-0 flex-1 md:flex md:items-center md:gap-3">
                <div className="truncate text-xs font-semibold text-ink md:w-44">
                  {block.title}
                </div>
                <div className="truncate text-[11px] text-muted md:w-64">
                  {block.detail ??
                    (commitment
                      ? "Fixed commitment"
                      : (KIND_LABELS[block.kind] ?? block.kind))}
                </div>
                <div className="text-[11px] text-muted md:w-20">
                  {minutes(block.minutes)}
                </div>
              </div>
              <div className="mr-3.5 flex items-center gap-1">
                {commitment ? (
                  <Chip tone="brand">Class</Chip>
                ) : status ? (
                  <Chip tone={status.tone}>{status.label}</Chip>
                ) : null}
                {!readOnly && open && block.plan_item_id && (
                  <>
                    {answerFirst ? (
                      <Link
                        href={`/student/learn/topic/${answerFirst}#easy-1`}
                        title="Done unlocks once you have answered one of this topic's questions today"
                        className="rounded-full px-2.5 py-1 text-[11px] font-semibold text-brand hover:bg-tile"
                      >
                        Answer one →
                      </Link>
                    ) : (
                      <button
                        disabled={busy === block.plan_item_id}
                        onClick={() => update(block.plan_item_id!, "completed")}
                        className="rounded-full px-2.5 py-1 text-[11px] font-semibold text-good hover:bg-good-soft"
                      >
                        Done
                      </button>
                    )}
                    <button
                      disabled={busy === block.plan_item_id}
                      onClick={() => update(block.plan_item_id!, "skipped")}
                      className="rounded-full px-2.5 py-1 text-[11px] font-semibold text-muted hover:bg-tile"
                    >
                      Skip
                    </button>
                  </>
                )}
              </div>
            </div>
            {why && (
              <div className="px-4 pb-2 text-[10.5px] leading-snug text-faint md:pl-[160px]">
                {why}
                {!readOnly && open && answerFirst ? " Answer one of its questions and it can be marked done." : ""}
              </div>
            )}
            {refused?.id === block.plan_item_id && (
              <div className="px-4 pb-2 text-[11px] font-medium text-rose-700 md:pl-[160px]">{refused.message}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
