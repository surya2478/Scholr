"use client";

import { useMe } from "@/components/AppShell";

// Parent pages act on one linked student. Phase 1 has one; the first link is used.
export function useLinkedStudent() {
  const me = useMe();
  const student = me?.linked_students[0] ?? null;
  return {
    student,
    id: student?.id ?? null,
    query: student ? `student_id=${student.id}` : "",
    has: (scope: string) => Boolean(student?.scopes.includes(scope)),
    subjects: student?.enrollments ?? [],
  };
}
