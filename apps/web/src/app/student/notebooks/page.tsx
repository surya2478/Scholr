"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { MathText } from "@/components/MathText";
import { Button, Card, Chip, ErrorNote } from "@/components/ui";
import { api, type Assessment, type Notebook, type NotebookItem } from "@/lib/api";
import {
  addToNotebook,
  createNotebook,
  deleteNotebook,
  loadNotebookItems,
  loadNotebooks,
  onNotebooksChanged,
  removeFromNotebook,
} from "@/lib/notebooks";

const NOTEBOOK_COLORS: Record<string, { bg: string; border: string; text: string; badge: string }> = {
  amber: { bg: "bg-amber-50", border: "border-slate-200", text: "text-amber-900", badge: "bg-amber-100 text-amber-800" },
  blue: { bg: "bg-blue-50", border: "border-blue-200", text: "text-blue-900", badge: "bg-blue-100 text-blue-800" },
  emerald: { bg: "bg-emerald-50", border: "border-emerald-200", text: "text-emerald-900", badge: "bg-emerald-100 text-emerald-800" },
  purple: { bg: "bg-purple-50", border: "border-purple-200", text: "text-purple-900", badge: "bg-purple-100 text-purple-800" },
  rose: { bg: "bg-rose-50", border: "border-rose-200", text: "text-rose-900", badge: "bg-rose-100 text-rose-800" },
};

export default function DigitalNotebooksPage() {
  const router = useRouter();
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [items, setItems] = useState<NotebookItem[]>([]);
  const [loadingItems, setLoadingItems] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [revealedAnswers, setRevealedAnswers] = useState<Record<string, boolean>>({});
  const [practicing, setPracticing] = useState(false);
  const [error, setError] = useState<unknown>(null);

  // Form state
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [icon, setIcon] = useState("📓");
  const [color, setColor] = useState("amber");

  async function refreshList() {
    try {
      const list = await loadNotebooks();
      setNotebooks(list);
      if (list.length > 0 && !selectedId) {
        setSelectedId(list[0].id);
      }
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshList();
    return onNotebooksChanged(() => void refreshList());
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setItems([]);
      return;
    }
    setLoadingItems(true);
    loadNotebookItems(selectedId)
      .then(setItems)
      .catch(setError)
      .finally(() => setLoadingItems(false));
  }, [selectedId]);

  async function handleCreateNotebook(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    try {
      const created = await createNotebook({
        title: title.trim(),
        description: description.trim() || undefined,
        icon,
        color,
      });
      setTitle("");
      setDescription("");
      setShowCreateModal(false);
      setSelectedId(created.id);
    } catch (err) {
      setError(err);
    }
  }

  async function handleDeleteNotebook(id: string) {
    if (!window.confirm("Are you sure you want to delete this digital notebook?")) return;
    try {
      await deleteNotebook(id);
      if (selectedId === id) {
        setSelectedId(notebooks.find((n) => n.id !== id)?.id ?? null);
      }
    } catch (err) {
      setError(err);
    }
  }

  async function handleRemoveItem(questionId: string) {
    if (!selectedId) return;
    try {
      await removeFromNotebook(selectedId, questionId);
      setItems((prev) => prev.filter((i) => i.question_item_id !== questionId));
    } catch (err) {
      setError(err);
    }
  }

  async function handlePracticeNotebook() {
    if (!selectedId) return;
    setPracticing(true);
    setError(null);
    try {
      const active = notebooks.find((n) => n.id === selectedId);
      const assessment = await api<Assessment>("/assessments/from-notebook", {
        method: "POST",
        json: {
          notebook_id: selectedId,
          title: `Practice: ${active?.title || "Notebook"}`,
          duration_minutes: 45,
        },
      });
      router.push(`/student/tests/${assessment.id}`);
    } catch (err) {
      setError(err);
      setPracticing(false);
    }
  }

  const activeNotebook = notebooks.find((n) => n.id === selectedId);
  const colorTheme = activeNotebook ? (NOTEBOOK_COLORS[activeNotebook.color] ?? NOTEBOOK_COLORS.amber) : NOTEBOOK_COLORS.amber;

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="rounded-2xl border border-slate-800 bg-gradient-to-r from-[#0B1528] via-[#122240] to-[#1E3A8A] p-6 md:p-7 text-white shadow-md">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-500/20 text-blue-200 text-[11px] font-bold uppercase tracking-wider border border-blue-400/30">
              <span>📓</span> Curated Question Collections &amp; Smart Revision
            </span>
            <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-white">
              Revision Notebooks &amp; Curated Sets
            </h1>
            <p className="text-xs md:text-sm text-slate-300 font-medium max-w-xl leading-relaxed">
              Organize high-yield questions into themed notebooks. Add personal margin notes, review step-by-step mark schemes, or launch a timed practice test directly from any notebook.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowCreateModal(true)}
            className="px-5 py-2.5 rounded-xl font-bold text-sm bg-blue-600 hover:bg-blue-500 text-white shadow-sm cursor-pointer transition-transform active:scale-95 shrink-0"
          >
            ＋ New Notebook
          </button>
        </div>
        {error ? <div className="mt-4"><ErrorNote error={error} /></div> : null}
      </div>

      {/* Notebook Tabs / Shelves */}
      {notebooks.length === 0 && !loading ? (
        <Card title="No Notebooks Yet">
          <div className="text-center py-10 space-y-4">
            <span className="text-5xl block">📓</span>
            <h3 className="text-lg font-fun font-bold text-slate-800">Create your first digital notebook</h3>
            <p className="text-xs text-slate-600 max-w-md mx-auto">
              Create notebooks for topics like &ldquo;Trigonometry Traps&rdquo;, &ldquo;Sociology 8-Markers&rdquo;, or &ldquo;Exam Morning Quick Revise&rdquo;.
            </p>
            <Button onClick={() => setShowCreateModal(true)}>Create a Notebook Now</Button>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Sidebar of Notebooks */}
          <div className="lg:col-span-1 space-y-2.5">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider block px-1">
              Your Notebooks ({notebooks.length})
            </span>
            <div className="flex flex-row lg:flex-col gap-2 overflow-x-auto pb-2 lg:pb-0">
              {notebooks.map((nb) => {
                const isSelected = nb.id === selectedId;
                const theme = NOTEBOOK_COLORS[nb.color] ?? NOTEBOOK_COLORS.amber;
                return (
                  <button
                    key={nb.id}
                    type="button"
                    onClick={() => setSelectedId(nb.id)}
                    className={`flex-shrink-0 lg:w-full text-left p-3.5 rounded-2xl border transition-all cursor-pointer ${
                      isSelected
                        ? `${theme.bg} ${theme.border} ${theme.text} shadow-xs font-bold ring-2 ring-amber-400/50`
                        : "bg-white border-slate-200 text-slate-700 hover:bg-slate-50"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="flex items-center gap-2 truncate">
                        <span className="text-lg">{nb.icon}</span>
                        <span className="text-sm font-fun truncate">{nb.title}</span>
                      </span>
                      <span className="text-[11px] px-2 py-0.5 rounded-full bg-white/80 border border-slate-200 font-mono">
                        {nb.item_count}
                      </span>
                    </div>
                    {nb.description && (
                      <p className="text-[11px] text-slate-500 font-normal line-clamp-1 mt-1 pl-7">
                        {nb.description}
                      </p>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Active Notebook View */}
          <div className="lg:col-span-3 space-y-4">
            {activeNotebook && (
              <div className={`p-5 rounded-3xl border-2 ${colorTheme.border} ${colorTheme.bg} space-y-3`}>
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-2xl">{activeNotebook.icon}</span>
                      <h2 className="text-xl font-fun font-bold text-slate-900">{activeNotebook.title}</h2>
                      <Chip tone="neutral">{items.length} questions</Chip>
                    </div>
                    {activeNotebook.description && (
                      <p className="text-xs text-slate-600 font-medium mt-1">
                        {activeNotebook.description}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      disabled={items.length === 0 || practicing}
                      onClick={handlePracticeNotebook}
                    >
                      {practicing ? "Generating Exam…" : "⚡ Practice This Notebook"}
                    </Button>
                    <button
                      type="button"
                      onClick={() => handleDeleteNotebook(activeNotebook.id)}
                      className="text-xs text-slate-400 hover:text-rose-600 p-2 rounded-xl hover:bg-white/80 cursor-pointer"
                      title="Delete notebook"
                    >
                      🗑️
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Questions List */}
            {loadingItems ? (
              <p className="text-sm text-slate-500 py-8 text-center">Loading questions in notebook…</p>
            ) : items.length === 0 ? (
              <Card title="Notebook is Empty">
                <div className="text-center py-8 space-y-3">
                  <span className="text-3xl block">🔖</span>
                  <p className="text-xs text-slate-600 max-w-sm mx-auto font-medium">
                    You haven&apos;t added questions to this notebook yet. Save questions directly while doing tests or lessons with the bookmark button!
                  </p>
                  <Link
                    href="/student/papers"
                    className="inline-block text-xs font-fun font-bold text-blue-600 hover:underline"
                  >
                    Browse Past Papers →
                  </Link>
                </div>
              </Card>
            ) : (
              <div className="space-y-4">
                {items.map((item, idx) => {
                  const q = item.question;
                  const isRevealed = Boolean(revealedAnswers[item.id]);
                  return (
                    <div
                      key={item.id}
                      className="p-5 rounded-3xl border border-slate-200 bg-white shadow-2xs space-y-3"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <span className="text-xs font-bold text-slate-500 font-mono">
                            Question {idx + 1} {q?.source_ref ? `· ${q.source_ref}` : ""}
                          </span>
                          <span className="ml-2 px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 text-[10px] font-bold">
                            {q?.marks ?? 1} marks
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() =>
                              setRevealedAnswers((prev) => ({ ...prev, [item.id]: !isRevealed }))
                            }
                            className="text-xs font-fun font-bold px-3 py-1 rounded-xl border border-slate-200 bg-amber-50/80 text-amber-900 hover:bg-amber-100 cursor-pointer"
                          >
                            {isRevealed ? "Hide Solution 🙈" : "Reveal Solution 👁️"}
                          </button>
                          <button
                            type="button"
                            onClick={() => handleRemoveItem(item.question_item_id)}
                            className="text-xs text-slate-400 hover:text-rose-600 p-1.5 rounded-lg cursor-pointer"
                            title="Remove from notebook"
                          >
                            ✕
                          </button>
                        </div>
                      </div>

                      {/* Question Stem */}
                      {q && (
                        <div className="text-sm text-slate-800 leading-relaxed font-medium bg-slate-50/60 p-4 rounded-2xl border border-slate-100">
                          <MathText text={q.stem} />
                        </div>
                      )}

                      {/* Student's Margin Notes */}
                      {item.student_notes && (
                        <div className="p-3 rounded-2xl bg-amber-50/70 border border-slate-200/90 text-xs text-amber-950">
                          <span className="font-fun font-bold block text-[10px] uppercase tracking-wider text-amber-800 mb-0.5">
                            My Note 💡
                          </span>
                          <p>{item.student_notes}</p>
                        </div>
                      )}

                      {/* Question Details & Actions */}
                      {isRevealed && q && (
                        <div className="p-4 rounded-2xl bg-indigo-50/60 border border-indigo-200 space-y-2.5 animate-in fade-in text-xs">
                          <div className="flex flex-wrap items-center gap-3">
                            {q.command_word && (
                              <span className="text-slate-700">
                                Command Word: <b className="text-indigo-900 capitalize">{q.command_word}</b>
                              </span>
                            )}
                            <span className="text-slate-700">
                              Calculator: <b className="text-indigo-900">{q.calculator_allowed === false ? "No" : "Allowed"}</b>
                            </span>
                          </div>
                          <div className="pt-2 border-t border-indigo-200/60 flex items-center gap-3">
                            <Link
                              href={`/student/tutor?prompt=Can you give me a structured hint and the key formula for this question: "${encodeURIComponent(q.stem)}"?`}
                              className="text-indigo-700 hover:text-indigo-800 font-bold underline"
                            >
                              Ask Tutor for Hints 💬 →
                            </Link>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-3xl border border-slate-200 shadow-2xl max-w-md w-full p-6 space-y-4 animate-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-lg font-fun font-bold text-slate-900">Create Digital Notebook 📓</h3>
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-slate-700 cursor-pointer"
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleCreateNotebook} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Title
                </label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Circle Theorems & Traps"
                  className="w-full text-sm px-3 py-2 rounded-xl border border-slate-200 focus:outline-none focus:border-amber-400"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Description (Optional)
                </label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g. Questions I slipped on in term 1"
                  className="w-full text-sm px-3 py-2 rounded-xl border border-slate-200 focus:outline-none focus:border-amber-400"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                    Icon
                  </label>
                  <select
                    value={icon}
                    onChange={(e) => setIcon(e.target.value)}
                    className="w-full text-sm px-3 py-2 rounded-xl border border-slate-200 focus:outline-none focus:border-amber-400"
                  >
                    <option value="📓">📓 Notebook</option>
                    <option value="🪤">🪤 Traps</option>
                    <option value="⚡">⚡ Quick Revise</option>
                    <option value="📐">📐 Geometry</option>
                    <option value="⭐">⭐ Must Master</option>
                    <option value="🧪">🧪 Science</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                    Color
                  </label>
                  <select
                    value={color}
                    onChange={(e) => setColor(e.target.value)}
                    className="w-full text-sm px-3 py-2 rounded-xl border border-slate-200 focus:outline-none focus:border-amber-400"
                  >
                    <option value="amber">Amber</option>
                    <option value="blue">Blue</option>
                    <option value="emerald">Emerald</option>
                    <option value="purple">Purple</option>
                    <option value="rose">Rose</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100 cursor-pointer"
                >
                  Cancel
                </button>
                <Button type="submit">Create Notebook</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
