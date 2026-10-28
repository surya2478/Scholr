"use client";

import { useMemo, useState } from "react";
import { Chip } from "@/components/ui";
import type { ObjectiveNode, SubjectTree, TopicNode } from "@/lib/api";

export type ChapterTopicSelectorProps = {
  tree: SubjectTree | null | undefined;
  loading?: boolean;
  selectedObjectiveIds: Set<string>;
  onChangeSelectedObjectives: (ids: Set<string>) => void;
  accentColor?: "orange" | "indigo";
};

// Helper: collect all objective IDs from a node and all its descendants
export function collectObjectiveIds(node: TopicNode): string[] {
  const ids: string[] = [];
  function walk(n: TopicNode) {
    if (n.objectives) {
      for (const obj of n.objectives) {
        ids.push(obj.id);
      }
    }
    if (n.children) {
      for (const child of n.children) {
        walk(child);
      }
    }
  }
  walk(node);
  return ids;
}

export function ChapterTopicSelector({
  tree,
  loading = false,
  selectedObjectiveIds,
  onChangeSelectedObjectives,
  accentColor = "orange",
}: ChapterTopicSelectorProps) {
  // Roots are depth 0 chapters (e.g., "1 Number", "2 Algebra and graphs")
  const chapters = useMemo(() => tree?.topics ?? [], [tree]);

  // Currently active chapter in the drill-down view
  const [activeChapterId, setActiveChapterId] = useState<string>("");
  // Set of subtopic IDs expanded to show individual learning objectives
  const [expandedSubtopics, setExpandedSubtopics] = useState<Set<string>>(new Set());
  // Search query to filter topics
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Default to first chapter if active is not set or not in chapters
  const currentChapter = useMemo(() => {
    if (chapters.length === 0) return null;
    return chapters.find((c) => c.id === activeChapterId) ?? chapters[0];
  }, [chapters, activeChapterId]);

  // Pre-calculate chapter objective maps for instant selection state
  const chapterMetrics = useMemo(() => {
    const map = new Map<string, { allIds: string[]; selectedCount: number }>();
    for (const ch of chapters) {
      const allIds = collectObjectiveIds(ch);
      let selectedCount = 0;
      for (const id of allIds) {
        if (selectedObjectiveIds.has(id)) selectedCount++;
      }
      map.set(ch.id, { allIds, selectedCount });
    }
    return map;
  }, [chapters, selectedObjectiveIds]);

  // Pre-calculate subtopic objective maps for the current chapter
  const subtopics = useMemo(() => {
    if (!currentChapter) return [];
    // If chapter has children, those are the subtopics (e.g., ch01, ch02)
    if (currentChapter.children && currentChapter.children.length > 0) {
      return currentChapter.children;
    }
    // If chapter has no children, treat the chapter itself as the single unit
    return [currentChapter];
  }, [currentChapter]);

  // Filter subtopics based on search
  const filteredSubtopics = useMemo(() => {
    if (!searchQuery.trim()) return subtopics;
    const q = searchQuery.toLowerCase();
    return subtopics.filter((sub) => {
      const matchName = sub.name.toLowerCase().includes(q) || sub.code.toLowerCase().includes(q);
      const matchObj = sub.objectives?.some(
        (o) => o.code.toLowerCase().includes(q) || o.statement.toLowerCase().includes(q)
      );
      return matchName || matchObj;
    });
  }, [subtopics, searchQuery]);

  // Toggle all objectives within a specific chapter
  function toggleChapter(chapterId: string) {
    const metrics = chapterMetrics.get(chapterId);
    if (!metrics) return;
    const next = new Set(selectedObjectiveIds);
    const allSelected = metrics.allIds.length > 0 && metrics.selectedCount === metrics.allIds.length;

    for (const id of metrics.allIds) {
      if (allSelected) {
        next.delete(id);
      } else {
        next.add(id);
      }
    }
    onChangeSelectedObjectives(next);
  }

  // Toggle all objectives within a specific subtopic
  function toggleSubtopic(subtopic: TopicNode) {
    const subtopicObjIds = collectObjectiveIds(subtopic);
    const next = new Set(selectedObjectiveIds);
    const allSelected = subtopicObjIds.every((id) => selectedObjectiveIds.has(id));

    for (const id of subtopicObjIds) {
      if (allSelected) {
        next.delete(id);
      } else {
        next.add(id);
      }
    }
    onChangeSelectedObjectives(next);
  }

  // Toggle an individual objective
  function toggleObjective(objectiveId: string) {
    const next = new Set(selectedObjectiveIds);
    if (next.has(objectiveId)) {
      next.delete(objectiveId);
    } else {
      next.add(objectiveId);
    }
    onChangeSelectedObjectives(next);
  }

  // Toggle expanding a subtopic to reveal objectives
  function toggleExpandSubtopic(subtopicId: string) {
    setExpandedSubtopics((prev) => {
      const next = new Set(prev);
      if (next.has(subtopicId)) next.delete(subtopicId);
      else next.add(subtopicId);
      return next;
    });
  }

  // Select all in full syllabus
  function selectAllSyllabus() {
    const all = new Set<string>();
    for (const ch of chapters) {
      for (const id of collectObjectiveIds(ch)) {
        all.add(id);
      }
    }
    onChangeSelectedObjectives(all);
  }

  // Clear all selections
  function clearAll() {
    onChangeSelectedObjectives(new Set());
  }

  // Count chapters with at least one selection
  const chaptersWithSelection = useMemo(() => {
    let count = 0;
    for (const metrics of chapterMetrics.values()) {
      if (metrics.selectedCount > 0) count++;
    }
    return count;
  }, [chapterMetrics]);

  if (loading) {
    return (
      <div className="p-8 text-center text-xs text-slate-500 font-medium">
        Loading syllabus chapters and topics…
      </div>
    );
  }

  if (chapters.length === 0) {
    return (
      <div className="p-6 text-center text-xs text-slate-500 font-medium">
        No chapters found for this subject.
      </div>
    );
  }

  const isOrange = accentColor === "orange";
  const activeChapterBorder = isOrange ? "border-orange-500" : "border-indigo-600";
  const activeChapterBg = isOrange ? "bg-blue-50/70" : "bg-indigo-50/70";
  const activeChapterText = isOrange ? "text-blue-950" : "text-indigo-950";
  const activeCheckboxBg = isOrange ? "bg-blue-600" : "bg-indigo-600";
  const ringFocus = isOrange ? "focus:border-blue-600" : "focus:border-indigo-600";

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-line-soft bg-white p-3 md:p-4 shadow-2xs">
      {/* Top Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-line-soft">
        <div className="flex items-center gap-2">
          <span className="text-xs font-fun font-bold text-slate-900">
            Syllabus Navigation:
          </span>
          <Chip tone={selectedObjectiveIds.size > 0 ? "good" : "neutral"}>
            {selectedObjectiveIds.size} topics selected across {chaptersWithSelection} chapters
          </Chip>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={selectAllSyllabus}
            className={`text-xs font-bold hover:underline ${isOrange ? "text-blue-600" : "text-indigo-600"}`}
          >
            Select All Full Syllabus
          </button>
          <span className="text-slate-300">·</span>
          <button
            type="button"
            onClick={clearAll}
            className="text-xs font-bold text-slate-500 hover:underline"
          >
            Clear All
          </button>
        </div>
      </div>

      {/* Main 2-Pane Split: Left Chapters, Right Subtopics */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3 min-h-[360px]">
        {/* Left Column: Chapters List (Numbers & Names) */}
        <div className="md:col-span-4 flex flex-col gap-1.5 max-h-[460px] overflow-y-auto pr-1">
          <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500 pb-1 px-1">
            Chapters ({chapters.length})
          </div>

          {chapters.map((ch) => {
            const metrics = chapterMetrics.get(ch.id) ?? { allIds: [], selectedCount: 0 };
            const isAllSelected = metrics.allIds.length > 0 && metrics.selectedCount === metrics.allIds.length;
            const isPartiallySelected = metrics.selectedCount > 0 && !isAllSelected;
            const isActive = currentChapter?.id === ch.id;

            return (
              <div
                key={ch.id}
                className={`group flex items-center justify-between rounded-xl border p-2.5 transition-all text-left cursor-pointer ${
                  isActive
                    ? `${activeChapterBorder} ${activeChapterBg} ${activeChapterText} shadow-xs font-bold`
                    : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 text-slate-700"
                }`}
                onClick={() => setActiveChapterId(ch.id)}
              >
                {/* Chapter Checkbox and Label */}
                <div className="flex items-center gap-2.5 min-w-0 flex-1">
                  <input
                    type="checkbox"
                    checked={isAllSelected}
                    ref={(el) => {
                      if (el) el.indeterminate = isPartiallySelected;
                    }}
                    onChange={(e) => {
                      e.stopPropagation();
                      toggleChapter(ch.id);
                    }}
                    className="h-4 w-4 rounded border-slate-300 text-blue-600 cursor-pointer focus:ring-0"
                    title={`Toggle all ${metrics.allIds.length} topics in this chapter`}
                  />

                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-fun font-bold truncate">
                      {ch.code ? `${ch.code}. ` : ""}
                      {ch.name}
                    </div>
                    <div className="text-[10px] text-slate-500 font-medium">
                      {ch.children?.length ? `${ch.children.length} subtopics · ` : ""}
                      {metrics.allIds.length} objectives
                    </div>
                  </div>
                </div>

                {/* Status Indicator */}
                <div className="ml-2 flex-shrink-0">
                  {isAllSelected ? (
                    <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100 text-[10px] font-bold text-emerald-800">
                      ✓
                    </span>
                  ) : isPartiallySelected ? (
                    <span className="rounded-md bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-800">
                      {metrics.selectedCount}/{metrics.allIds.length}
                    </span>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>

        {/* Right Column: Subtopics & Learning Objectives Checklist */}
        <div className="md:col-span-8 flex flex-col gap-2 rounded-xl border border-slate-200 bg-slate-50/50 p-3 max-h-[460px] overflow-y-auto">
          {currentChapter ? (
            <>
              {/* Active Chapter Header */}
              <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-200/80">
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Selected Chapter
                  </div>
                  <h3 className="text-sm font-fun font-bold text-slate-900">
                    {currentChapter.code ? `Chapter ${currentChapter.code}: ` : ""}
                    {currentChapter.name}
                  </h3>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => toggleChapter(currentChapter.id)}
                    className={`rounded-lg px-2.5 py-1 text-[11px] font-bold transition border ${
                      isOrange
                        ? "border-orange-300 bg-blue-50 text-blue-800 hover:bg-orange-200"
                        : "border-indigo-300 bg-indigo-100 text-indigo-800 hover:bg-indigo-200"
                    }`}
                  >
                    {chapterMetrics.get(currentChapter.id)?.selectedCount ===
                    chapterMetrics.get(currentChapter.id)?.allIds.length
                      ? "Deselect All in Chapter"
                      : "Select All in Chapter"}
                  </button>
                </div>
              </div>

              {/* Search filter within chapter */}
              <div className="relative pt-1">
                <input
                  type="text"
                  placeholder={`Search topics or objectives in Chapter ${currentChapter.name}…`}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className={`h-8 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-800 placeholder-slate-400 focus:outline-none ${ringFocus}`}
                />
              </div>

              {/* Subtopics List */}
              <div className="flex flex-col gap-2 pt-1">
                {filteredSubtopics.length === 0 ? (
                  <p className="text-xs text-slate-500 p-4 text-center">
                    No topics matching &ldquo;{searchQuery}&rdquo;.
                  </p>
                ) : (
                  filteredSubtopics.map((sub) => {
                    const subObjIds = collectObjectiveIds(sub);
                    const selectedInSub = subObjIds.filter((id) => selectedObjectiveIds.has(id)).length;
                    const isAllSubSelected = subObjIds.length > 0 && selectedInSub === subObjIds.length;
                    const isPartiallySubSelected = selectedInSub > 0 && !isAllSubSelected;
                    const isExpanded = expandedSubtopics.has(sub.id);

                    return (
                      <div
                        key={sub.id}
                        className="rounded-xl border border-slate-200 bg-white shadow-2xs overflow-hidden"
                      >
                        {/* Subtopic Main Row */}
                        <div className="flex items-center justify-between gap-2 p-2.5 hover:bg-slate-50/80 transition">
                          <label className="flex items-center gap-2.5 min-w-0 flex-1 cursor-pointer select-none">
                            <input
                              type="checkbox"
                              checked={isAllSubSelected}
                              ref={(el) => {
                                if (el) el.indeterminate = isPartiallySubSelected;
                              }}
                              onChange={() => toggleSubtopic(sub)}
                              className="h-4 w-4 rounded border-slate-300 text-blue-600 cursor-pointer focus:ring-0"
                            />
                            <div className="min-w-0 flex-1">
                              <span className="text-xs font-fun font-bold text-slate-900 block truncate">
                                {sub.code ? `${sub.code} ` : ""}
                                {sub.name}
                              </span>
                              <span className="text-[10px] text-slate-500 font-medium">
                                {subObjIds.length} learning objective{subObjIds.length === 1 ? "" : "s"}
                                {selectedInSub > 0 && (
                                  <span className="text-emerald-700 font-bold ml-1">
                                    ({selectedInSub} selected)
                                  </span>
                                )}
                              </span>
                            </div>
                          </label>

                          {/* Expand to see individual objectives */}
                          {sub.objectives && sub.objectives.length > 0 && (
                            <button
                              type="button"
                              onClick={() => toggleExpandSubtopic(sub.id)}
                              className="rounded-md px-2 py-1 text-[11px] font-bold text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition"
                              title="View and select individual objectives"
                            >
                              {isExpanded ? "Hide Objectives ▲" : `View Objectives (${sub.objectives.length}) ▼`}
                            </button>
                          )}
                        </div>

                        {/* Objectives Drill-Down Panel */}
                        {isExpanded && sub.objectives && sub.objectives.length > 0 && (
                          <div className="border-t border-slate-100 bg-slate-50/70 p-2.5 flex flex-col gap-1.5">
                            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider px-1">
                              Individual Learning Objectives:
                            </div>
                            {sub.objectives.map((obj) => {
                              const isObjSelected = selectedObjectiveIds.has(obj.id);
                              return (
                                <label
                                  key={obj.id}
                                  className={`flex items-start gap-2 rounded-lg p-2 text-xs transition cursor-pointer select-none ${
                                    isObjSelected
                                      ? "bg-white border border-emerald-300 shadow-2xs text-slate-900"
                                      : "bg-white/60 border border-transparent hover:bg-white text-slate-700"
                                  }`}
                                >
                                  <input
                                    type="checkbox"
                                    checked={isObjSelected}
                                    onChange={() => toggleObjective(obj.id)}
                                    className="h-3.5 w-3.5 mt-0.5 rounded border-slate-300 text-blue-600 cursor-pointer focus:ring-0"
                                  />
                                  <div className="min-w-0 flex-1">
                                    <span className="font-mono font-bold text-[11px] text-slate-800 mr-1.5">
                                      {obj.code}
                                    </span>
                                    <span className="text-[11px] text-slate-600 leading-relaxed">
                                      {obj.statement}
                                    </span>
                                  </div>
                                </label>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </>
          ) : (
            <div className="p-8 text-center text-xs text-slate-400">
              Select a chapter on the left to view its topics.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
