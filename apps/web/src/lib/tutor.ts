// One way to open the Tutor on something she is looking at (docs/STUDENT-APP.md, step 3). The session is
// scoped to the subject and, when known, the objective, so retrieval and the answer stay on that topic.
export function tutorHref({
  subjectId,
  objectiveId,
  about,
  ask,
}: {
  subjectId: string;
  objectiveId?: string | null;
  about?: string;
  ask: string;
}): string {
  const q = about ? `About "${about}": ${ask}` : ask;
  const params = new URLSearchParams({ subject: subjectId, q: q.slice(0, 500) });
  if (objectiveId) params.set("objective", objectiveId);
  return `/student/tutor?${params.toString()}`;
}
