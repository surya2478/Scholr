"use client";

import { useEffect, useState } from "react";
import type { BookmarkTag, Question } from "@/lib/api";
import {
  BOOKMARK_TAG_META,
  cachedBookmarks,
  loadBookmarks,
  onBookmarksChanged,
  removeBookmark,
  saveBookmark,
} from "@/lib/bookmarks";

// Save a question to revise later, with a tag and a note of her own. Kept in her record, not the browser.
export function BookmarkButton({ question }: { question: Question }) {
  const find = () => cachedBookmarks().find((b) => b.question_item_id === question.id);
  const [bookmark, setBookmark] = useState(find);
  const [showTagMenu, setShowTagMenu] = useState(false);
  const [note, setNote] = useState(bookmark?.note ?? "");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const refresh = () => {
      const b = cachedBookmarks().find((x) => x.question_item_id === question.id);
      setBookmark(b);
      setNote(b?.note ?? "");
    };
    void loadBookmarks().then(refresh, () => setFailed(true));
    return onBookmarksChanged(refresh);
  }, [question.id]);

  async function run(action: () => Promise<void>) {
    setFailed(false);
    try {
      await action();
    } catch {
      setFailed(true);
    }
  }

  function handleToggle() {
    if (bookmark) {
      setShowTagMenu(false);
      void run(() => removeBookmark(question.id));
    } else {
      setShowTagMenu(true);
      void run(() => saveBookmark(question, "must_revise", null));
    }
  }

  function handleSelectTag(tag: BookmarkTag) {
    void run(() => saveBookmark(question, tag, note));
  }

  const isSaved = !!bookmark;
  const currentTagMeta = bookmark ? BOOKMARK_TAG_META[bookmark.tag] : null;

  return (
    <div className="relative inline-flex items-center gap-1.5">
      <button
        type="button"
        onClick={handleToggle}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-fun font-bold transition-all cursor-pointer border shadow-2xs ${
          isSaved
            ? "bg-amber-100 text-amber-900 border-amber-300 hover:bg-amber-200"
            : "bg-white/80 text-slate-600 border-slate-300 hover:bg-slate-100 hover:text-slate-900"
        }`}
        title={isSaved ? "Remove from your saved questions" : "Save this question to revise later"}
      >
        <span>{isSaved ? "🔖" : "🏷️"}</span>
        <span>{isSaved ? currentTagMeta?.label : "Save"}</span>
      </button>

      {isSaved && (
        <button
          type="button"
          onClick={() => setShowTagMenu((prev) => !prev)}
          className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-amber-200/90 text-amber-900 hover:bg-amber-300 cursor-pointer"
          title="Change the tag or add a note"
        >
          ⚙️
        </button>
      )}

      {failed && <span className="text-[10px] font-semibold text-rose-700">Not saved — try again</span>}

      {showTagMenu && isSaved && (
        <div className="absolute right-0 top-full mt-2 w-64 p-3 rounded-2xl border border-slate-200 bg-white shadow-xl z-30 space-y-2.5 text-left animate-in fade-in zoom-in-95">
          <div className="flex items-center justify-between border-b border-slate-100 pb-1.5">
            <span className="text-xs font-fun font-bold text-slate-800">
              Why you saved it
            </span>
            <button
              type="button"
              onClick={() => setShowTagMenu(false)}
              className="text-xs text-slate-400 hover:text-slate-700 cursor-pointer"
            >
              ✕
            </button>
          </div>

          <div className="space-y-1.5">
            {(Object.keys(BOOKMARK_TAG_META) as BookmarkTag[]).map((tagKey) => {
              const meta = BOOKMARK_TAG_META[tagKey];
              const isSelected = bookmark?.tag === tagKey;
              return (
                <button
                  key={tagKey}
                  type="button"
                  onClick={() => handleSelectTag(tagKey)}
                  className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-xl text-xs font-medium border transition-all cursor-pointer text-left ${
                    isSelected
                      ? `${meta.color} font-bold shadow-2xs`
                      : "border-slate-200 hover:bg-slate-50 text-slate-700"
                  }`}
                >
                  <span className="flex items-center gap-1.5">
                    <span>{meta.emoji}</span>
                    <span>{meta.label}</span>
                  </span>
                  {isSelected && <span className="text-[11px]">✓</span>}
                </button>
              );
            })}
          </div>

          <div className="pt-1.5 border-t border-slate-100">
            <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">
              Your note
            </label>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              onBlur={() => {
                if (bookmark && note !== (bookmark.note ?? "")) void run(() => saveBookmark(question, bookmark.tag, note));
              }}
              maxLength={500}
              placeholder="e.g. Watch negative sign in step 2"
              className="w-full text-xs px-2 py-1.5 rounded-lg border border-slate-200 focus:outline-none focus:border-amber-400"
            />
          </div>

          <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
            <span className="text-slate-500 font-medium">Digital Notebooks</span>
            <a
              href="/student/notebooks"
              className="text-amber-600 hover:text-amber-700 font-bold underline"
            >
              Organize 📓 →
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

