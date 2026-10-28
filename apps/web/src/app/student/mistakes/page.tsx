"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { BugHunter } from "@/components/BugHunter";
import { MathText } from "@/components/MathText";
import { Card, Chip, Empty, ErrorNote } from "@/components/ui";
import { api, type Assessment, type AutopsyEntry, type Bookmark, type BookmarkTag, type Mistake } from "@/lib/api";
import { BOOKMARK_TAG_META, loadBookmarks, onBookmarksChanged, removeBookmark } from "@/lib/bookmarks";
import { shortDate } from "@/lib/format";
import { tutorHref } from "@/lib/tutor";
import { useApi } from "@/lib/useApi";

const FILTERS = [
  { value: "", label: "All" },
  { value: "open", label: "Open" },
  { value: "improving", label: "Improving" },
  { value: "resolved", label: "Fixed" },
];

export default function Mistakes() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"tracker" | "bughunter" | "diary" | "traps">("tracker");
  const [status, setStatus] = useState("");
  const [diaryCategory, setDiaryCategory] = useState("");
  const [trapFilter, setTrapFilter] = useState<string>("");
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
  const [bookmarkError, setBookmarkError] = useState<unknown>(null);
  const [drilling, setDrilling] = useState(false);
  const [drillError, setDrillError] = useState<string | null>(null);

  const list = useApi<Mistake[]>(`/mistakes${status ? `?status=${status}` : ""}`);
  const autopsies = useApi<AutopsyEntry[]>("/evaluations/autopsies");

  useEffect(() => {
    const refresh = () => void loadBookmarks().then(setBookmarks, setBookmarkError);
    refresh();
    return onBookmarksChanged(refresh);
  }, []);

  async function handleKillMistakesDrill() {
    const firstSubjectId = list.data?.find((m) => m.subject_id)?.subject_id;
    if (!firstSubjectId) {
      setDrillError("No open mistakes found to drill!");
      return;
    }
    setDrilling(true);
    setDrillError(null);
    try {
      const assessment = await api<Assessment>("/assessments/from-mistakes", {
        method: "POST",
        json: {
          subject_id: firstSubjectId,
          title: "Mistake Killer Drill 🎯",
          limit: 5,
        },
      });
      router.push(`/student/tests/${assessment.id}`);
    } catch {
      setDrillError("Could not generate drill. Ensure you have open mistake objectives.");
      setDrilling(false);
    }
  }

  const filteredAutopsies = (autopsies.data ?? []).filter(
    (a) => !diaryCategory || a.category === diaryCategory
  );

  const filteredBookmarks = bookmarks.filter(
    (b) => !trapFilter || b.tag === trapFilter
  );

  return (
    <div className="space-y-6">
      {/* Senior Academic Header */}
      <div className="rounded-2xl border border-slate-800 bg-gradient-to-r from-[#0B1528] via-[#122240] to-[#1E3A8A] p-6 md:p-7 text-white shadow-md">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-rose-500/20 text-rose-200 text-[11px] font-bold uppercase tracking-wider border border-rose-400/30">
              <span>🛠️</span> Diagnostic Feedback Loop &amp; Trap Immunity
            </span>
            <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-white">
              Error Log, Autopsy &amp; Trap Repair
            </h1>
            <p className="text-xs md:text-sm text-slate-300 font-medium max-w-xl leading-relaxed">
              Track recurring syllabus vulnerabilities, review your personal error autopsies, revisit bookmarked questions, or launch a 5-question remediation drill.
            </p>
          </div>
          <div className="flex flex-col items-stretch sm:items-end gap-2 shrink-0">
            <button
              type="button"
              disabled={drilling}
              onClick={handleKillMistakesDrill}
              className="px-4 py-2.5 rounded-xl font-bold text-xs bg-rose-600 hover:bg-rose-500 text-white shadow-sm cursor-pointer transition-transform active:scale-95 disabled:opacity-50"
            >
              {drilling ? "Assembling Drill…" : "🎯 Launch 5-Question Remediation Drill"}
            </button>
            <Link
              href="/student/notebooks"
              className="text-xs font-bold text-amber-300 hover:text-amber-200 underline text-center sm:text-right"
            >
              Open Revision Notebooks 📓 →
            </Link>
          </div>
        </div>
        {drillError && (
          <div className="mt-3 text-xs text-rose-100 font-bold bg-rose-950/60 p-2.5 rounded-xl border border-rose-400/40">
            {drillError}
          </div>
        )}

        {/* Tab Switcher */}
        <div className="flex flex-wrap gap-2 mt-5 pt-4 border-t border-white/15">
          <button
            type="button"
            onClick={() => setActiveTab("tracker")}
            className={`px-4 py-2 rounded-xl font-bold text-xs transition-all cursor-pointer ${
              activeTab === "tracker"
                ? "bg-blue-600 text-white shadow-xs"
                : "bg-white/10 text-slate-200 hover:bg-white/15 border border-white/15"
            }`}
          >
            📋 Syllabus Error Tracker ({list.data?.length ?? 0})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("diary")}
            className={`px-4 py-2 rounded-xl font-bold text-xs transition-all cursor-pointer ${
              activeTab === "diary"
                ? "bg-purple-600 text-white shadow-xs"
                : "bg-white/10 text-slate-200 hover:bg-white/15 border border-white/15"
            }`}
          >
            📔 Personal Error Autopsies ({autopsies.data?.length ?? 0})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("traps")}
            className={`px-4 py-2 rounded-xl font-bold text-xs transition-all cursor-pointer ${
              activeTab === "traps"
                ? "bg-amber-600 text-white shadow-xs"
                : "bg-white/10 text-slate-200 hover:bg-white/15 border border-white/15"
            }`}
          >
            🔖 Saved Questions ({bookmarks.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("bughunter")}
            className={`px-4 py-2 rounded-xl font-bold text-xs transition-all cursor-pointer ${
              activeTab === "bughunter"
                ? "bg-blue-600 text-white shadow-xs"
                : "bg-white/10 text-slate-200 hover:bg-white/15 border border-white/15"
            }`}
          >
            🔬 Chief Examiner: Find the Flaw
          </button>
        </div>
      </div>

      {activeTab === "bughunter" ? (
        <BugHunter />
      ) : activeTab === "diary" ? (
        <Card
          title="📔 Personal Error Autopsy Log"
          subtitle="Your own diagnostic rules recorded after losing marks on a question. Reviewing these before an assessment prevents repeat mistakes."
          tone="purple"
        >
          <div className="flex flex-wrap gap-2 pt-1">
            {[
              { value: "", label: "All Categories" },
              { value: "conceptual", label: "🧠 Conceptual" },
              { value: "calculation", label: "✏️ Calculation" },
              { value: "misreading", label: "🔍 Misreading" },
              { value: "strategy", label: "⏱️ Strategic" },
            ].map((f) => (
              <button
                key={f.value}
                onClick={() => setDiaryCategory(f.value)}
                className={`rounded-2xl px-3.5 py-1.5 text-xs font-fun font-bold transition-all cursor-pointer ${
                  diaryCategory === f.value
                    ? "bg-purple-600 text-white shadow-xs"
                    : "bg-purple-50/70 border border-purple-200/80 text-purple-900 hover:bg-white"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {autopsies.error ? <ErrorNote error={autopsies.error} /> : null}
          {filteredAutopsies.length === 0 && (
            <Empty>
              No error diary entries yet. When you conduct an error autopsy in Practice Lab or Tests, your personal rules will appear here! 🌟
            </Empty>
          )}

          <ul className="flex flex-col gap-3.5 pt-2">
            {filteredAutopsies.map((entry) => (
              <li
                key={entry.evaluation_id}
                className="flex flex-col gap-2.5 rounded-2xl border-2 border-purple-200/80 bg-gradient-to-br from-white via-[#FAF7FD] to-purple-50/40 p-4 shadow-2xs hover:border-purple-300 transition-colors"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-purple-100 pb-2">
                  <div className="flex items-center gap-2 text-xs">
                    {entry.objective_code && (
                      <span className="font-fun font-bold text-purple-800 bg-purple-100 px-2 py-0.5 rounded-md">
                        Topic {entry.objective_code}
                      </span>
                    )}
                    <span className="text-slate-400 font-medium">
                      Recorded on {shortDate(entry.recorded_at)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-600">
                      Scored {entry.marks_awarded} / {entry.marks_available} Marks
                    </span>
                    <Chip tone="brand">
                      {entry.category.toUpperCase()}
                    </Chip>
                  </div>
                </div>

                <div className="text-xs text-slate-600 font-medium line-clamp-2">
                  <span className="font-bold text-slate-800">Question: </span>
                  <MathText text={entry.stem} />
                </div>

                <div className="p-3 rounded-xl bg-purple-100/70 border border-purple-200 text-xs">
                  <div className="text-[10px] font-fun font-bold uppercase tracking-wider text-purple-900 mb-0.5">
                    💡 My Personal Rule for Next Time:
                  </div>
                  <div className="text-sm font-semibold text-purple-950 italic">
                    &ldquo;{entry.takeaway}&rdquo;
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      ) : activeTab === "traps" ? (
        <Card
          title="🔖 Saved questions"
          subtitle="Questions you saved to revise, with your own tag and note. They are kept in your record, so they are here on any device."
          tone="amber"
        >
          <div className="flex flex-wrap gap-2 pt-1">
            <button
              type="button"
              onClick={() => setTrapFilter("")}
              className={`rounded-2xl px-3.5 py-1.5 text-xs font-fun font-bold transition-all cursor-pointer ${
                !trapFilter
                  ? "bg-amber-600 text-white shadow-xs"
                  : "bg-amber-50 border border-slate-200 text-amber-900 hover:bg-white"
              }`}
            >
              All saved ({bookmarks.length})
            </button>
            {(Object.keys(BOOKMARK_TAG_META) as BookmarkTag[]).map((tagKey) => {
              const meta = BOOKMARK_TAG_META[tagKey];
              const count = bookmarks.filter((b) => b.tag === tagKey).length;
              return (
                <button
                  key={tagKey}
                  type="button"
                  onClick={() => setTrapFilter(tagKey)}
                  className={`rounded-2xl px-3.5 py-1.5 text-xs font-fun font-bold transition-all cursor-pointer ${
                    trapFilter === tagKey
                      ? "bg-amber-600 text-white shadow-xs"
                      : "bg-amber-50 border border-slate-200 text-amber-900 hover:bg-white"
                  }`}
                >
                  {meta.emoji} {meta.label} ({count})
                </button>
              );
            })}
          </div>

          {bookmarkError ? <ErrorNote error={bookmarkError} /> : null}
          {filteredBookmarks.length === 0 ? (
            <Empty>
              No saved questions here yet. Tap &ldquo;Save&rdquo; on any question you answer to keep it for revision.
            </Empty>
          ) : (
            <ul className="flex flex-col gap-3.5 pt-2">
              {filteredBookmarks.map((item) => {
                const meta = BOOKMARK_TAG_META[item.tag];
                return (
                  <li
                    key={item.question_item_id}
                    className="flex flex-col gap-2.5 rounded-2xl border-2 border-slate-200/90 bg-gradient-to-br from-white via-[#FFFDF8] to-amber-50/40 p-4 shadow-2xs hover:border-blue-400 transition-colors"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2">
                      <div className="flex items-center gap-2 text-xs">
                        <span className={`px-2.5 py-0.5 rounded-full text-xs font-fun font-bold border ${meta.color}`}>
                          {meta.emoji} {meta.label}
                        </span>
                        <span className="text-slate-400 font-medium">
                          Saved on {shortDate(item.saved_at)}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {item.marks > 0 && (
                          <span className="text-xs font-bold text-amber-800 bg-amber-100/80 px-2 py-0.5 rounded-md">
                            {item.marks} Mark{item.marks === 1 ? "" : "s"}
                          </span>
                        )}
                        <button
                          type="button"
                          onClick={() => void removeBookmark(item.question_item_id).catch(setBookmarkError)}
                          className="text-xs text-slate-400 hover:text-rose-600 font-bold px-2 py-0.5 rounded-md hover:bg-rose-50 transition-colors cursor-pointer"
                          title="Remove from bank"
                        >
                          Remove ✕
                        </button>
                      </div>
                    </div>

                    <div className="text-sm text-slate-800 font-medium">
                      <MathText text={item.stem} />
                    </div>

                    {item.note && (
                      <div className="p-2.5 rounded-xl bg-amber-100/70 border border-slate-200 text-xs">
                        <span className="font-fun font-bold text-amber-900">📝 My note: </span>
                        <span className="text-amber-950 font-medium italic">&ldquo;{item.note}&rdquo;</span>
                      </div>
                    )}

                    <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-xs">
                      <Link
                        href={tutorHref({
                          subjectId: item.subject_id,
                          about: item.stem,
                          ask: `I saved this question to revise (${meta.label}). Can you help me see how to approach it?`,
                        })}
                        className="font-fun font-bold text-blue-600 hover:underline"
                      >
                        🦉 Ask the Tutor about it
                      </Link>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      ) : (
        <Card title="Mistake Tracker" subtitle="Filter by status to target what to practice next">
          <div className="flex flex-wrap gap-2 pt-1">
            {FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => setStatus(f.value)}
                className={`rounded-2xl px-4 py-1.5 text-xs font-fun font-bold transition-all cursor-pointer ${
                  status === f.value
                    ? "bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-xs"
                    : "bg-amber-50/70 border border-slate-200/90 text-slate-600 hover:text-slate-900 hover:bg-white"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {list.error ? <ErrorNote error={list.error} /> : null}
          {list.data?.length === 0 && (
            <Empty>Awesome! No mistakes found in this category. Keep up the brilliant focus! 🌟</Empty>
          )}

          <ul className="flex flex-col gap-3 pt-2">
            {list.data?.map((m) => (
              <li
                key={m.id}
                className="flex flex-wrap items-start gap-3 rounded-2xl border-2 border-slate-200/90 bg-white p-4 shadow-2xs hover:border-blue-400 transition-colors"
              >
                <div className="min-w-0 flex-1 space-y-1">
                  <MathText text={m.description} className="text-sm font-semibold text-slate-900" />
                  <div className="text-xs text-slate-500 font-medium">
                    {m.objective_code ? (
                      <span className="font-bold text-blue-700">Topic {m.objective_code} · </span>
                    ) : (
                      ""
                    )}
                    Seen {m.occurrences} time{m.occurrences === 1 ? "" : "s"} · last on {shortDate(m.last_seen)}
                  </div>
                  <div className="flex flex-wrap gap-3 pt-1 text-xs font-fun font-bold">
                    {m.objective_id && (
                      <Link href={`/student/learn/topic/${m.objective_id}`} className="text-blue-600 hover:underline">
                        📘 Open the topic
                      </Link>
                    )}
                    <Link
                      href={tutorHref({
                        subjectId: m.subject_id,
                        objectiveId: m.objective_id,
                        ask: `I keep making this mistake: ${m.description} How do I avoid it?`,
                      })}
                      className="text-blue-600 hover:underline"
                    >
                      🦉 Ask the Tutor about this mistake
                    </Link>
                  </div>
                </div>
                <Chip tone={m.severity === "high" ? "alert" : m.severity === "medium" ? "warn" : "neutral"}>
                  {m.severity === "high" ? "High Priority ⚠️" : m.severity === "medium" ? "Medium" : "Minor"}
                </Chip>
                <Chip tone={m.status === "resolved" ? "good" : m.status === "improving" ? "brand" : "neutral"}>
                  {m.status === "resolved" ? "Fixed ✓" : m.status === "improving" ? "Improving 📈" : m.status}
                </Chip>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
