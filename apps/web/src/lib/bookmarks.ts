// Questions she saved to revise. They live in her record on the server (GET/PUT/DELETE /bookmarks), so they follow
// her from phone to home; this module keeps one shared copy for the page and tells components when it changes.

import { api, type Bookmark, type BookmarkTag } from "@/lib/api";

export const BOOKMARK_TAG_META: Record<BookmarkTag, { label: string; emoji: string; color: string }> = {
  examiner_trap: { label: "Easy to slip on", emoji: "🪤", color: "bg-rose-100 text-rose-800 border-rose-300" },
  calc_heavy: { label: "Long calculation", emoji: "⏳", color: "bg-amber-100 text-amber-800 border-amber-300" },
  must_revise: { label: "Revise before the exam", emoji: "⭐", color: "bg-purple-100 text-purple-800 border-purple-300" },
};

const EVENT = "scholr:bookmarks-updated";
let cache: Bookmark[] | null = null;
let loading: Promise<Bookmark[]> | null = null;

function changed(next: Bookmark[]): void {
  cache = next;
  window.dispatchEvent(new CustomEvent(EVENT));
}

/** Her saved questions, fetched once and then kept in step with her changes. */
export function loadBookmarks(): Promise<Bookmark[]> {
  if (cache) return Promise.resolve(cache);
  loading ??= api<Bookmark[]>("/bookmarks")
    .then((rows) => {
      changed(rows);
      return rows;
    })
    .finally(() => {
      loading = null;
    });
  return loading;
}

export function cachedBookmarks(): Bookmark[] {
  return cache ?? [];
}

export function onBookmarksChanged(listener: () => void): () => void {
  window.addEventListener(EVENT, listener);
  return () => window.removeEventListener(EVENT, listener);
}

/** Save a question, or change its tag or note. The server keeps one bookmark per question. */
export async function saveBookmark(
  question: { id: string; subject_id: string; source_ref: string | null; stem: string; marks: number },
  tag: BookmarkTag,
  note: string | null,
): Promise<void> {
  await api(`/bookmarks/${question.id}`, { method: "PUT", json: { tag, note } });
  const current = await loadBookmarks();
  const kept = current.find((b) => b.question_item_id === question.id);
  const row: Bookmark = {
    question_item_id: question.id,
    subject_id: question.subject_id,
    source_ref: question.source_ref,
    stem: question.stem,
    marks: question.marks,
    tag,
    note: note?.trim() || null,
    saved_at: kept?.saved_at ?? new Date().toISOString(),
  };
  changed(kept ? current.map((b) => (b.question_item_id === question.id ? row : b)) : [row, ...current]);
}

export async function removeBookmark(questionId: string): Promise<void> {
  await api(`/bookmarks/${questionId}`, { method: "DELETE" });
  changed((await loadBookmarks()).filter((b) => b.question_item_id !== questionId));
}
