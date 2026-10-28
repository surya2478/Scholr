// Digital Notebooks client state and helper functions.
// Allows creating unlimited notebooks, adding questions with student reflection notes,
// and triggering custom practice assessments.

import { api, type Notebook, type NotebookItem, type Question } from "@/lib/api";

const EVENT = "scholr:notebooks-updated";
let cache: Notebook[] | null = null;
let loading: Promise<Notebook[]> | null = null;

function notify(next: Notebook[]): void {
  cache = next;
  window.dispatchEvent(new CustomEvent(EVENT));
}

export function loadNotebooks(): Promise<Notebook[]> {
  if (cache) return Promise.resolve(cache);
  loading ??= api<Notebook[]>("/notebooks")
    .then((rows) => {
      notify(rows);
      return rows;
    })
    .finally(() => {
      loading = null;
    });
  return loading;
}

export function cachedNotebooks(): Notebook[] {
  return cache ?? [];
}

export function onNotebooksChanged(listener: () => void): () => void {
  window.addEventListener(EVENT, listener);
  return () => window.removeEventListener(EVENT, listener);
}

export async function createNotebook(data: {
  title: string;
  description?: string;
  icon?: string;
  color?: string;
  subject_id?: string;
}): Promise<Notebook> {
  const created = await api<Notebook>("/notebooks", { method: "POST", json: data });
  cache = null;
  const list = await loadNotebooks();
  notify(list);
  return created;
}

export async function deleteNotebook(id: string): Promise<void> {
  await api(`/notebooks/${id}`, { method: "DELETE" });
  cache = null;
  const list = await loadNotebooks();
  notify(list);
}

export async function loadNotebookItems(notebookId: string): Promise<NotebookItem[]> {
  return api<NotebookItem[]>(`/notebooks/${notebookId}/items`);
}

export async function addToNotebook(
  notebookId: string,
  questionId: string,
  studentNotes?: string
): Promise<NotebookItem> {
  const item = await api<NotebookItem>(`/notebooks/${notebookId}/items`, {
    method: "POST",
    json: { question_item_id: questionId, student_notes: studentNotes },
  });
  cache = null;
  await loadNotebooks();
  return item;
}

export async function removeFromNotebook(notebookId: string, questionId: string): Promise<void> {
  await api(`/notebooks/${notebookId}/items/${questionId}`, { method: "DELETE" });
  cache = null;
  await loadNotebooks();
}
