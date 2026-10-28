export const LEVELS = ["Not introduced", "Introduced", "Developing", "Competent", "Mastered", "Advanced"] as const;

export function minutes(total: number): string {
  if (total < 60) return `${total} min`;
  const h = Math.floor(total / 60);
  const m = total % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

export function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
}

export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

const RRULE_DAYS: Record<string, string> = {
  MO: "Mon",
  TU: "Tue",
  WE: "Wed",
  TH: "Thu",
  FR: "Fri",
  SA: "Sat",
  SU: "Sun",
};

// The days a weekly commitment falls on, read from its own recurrence rule: "FREQ=WEEKLY;BYDAY=MO,TH" -> "Mon · Thu".
// Anything the rule does not say is not invented: a daily rule reads "Every day", and a rule we cannot read returns "".
export function commitmentDays(rrule: string): string {
  if (/FREQ=DAILY/.test(rrule)) return "Every day";
  const byday = /BYDAY=([A-Z,]+)/.exec(rrule);
  if (!byday) return "";
  return byday[1]
    .split(",")
    .map((d) => RRULE_DAYS[d.trim()])
    .filter(Boolean)
    .join(" · ");
}

export function greeting(now = new Date()): string {
  const h = now.getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

export const KIND_LABELS: Record<string, string> = {
  assessment: "Test prep",
  mistake_fix: "Fix a mistake",
  revision: "Revision",
  school_topic: "School topic",
  reinforcement: "From your IIT class",
  practice: "Practice",
  challenge: "Challenge",
  baseline: "Baseline test",
  post: "Post-test",
  retention: "Retention test",
  quiz: "Quiz",
  exam_style: "Exam-style",
  topic_exam: "Topic exam",
};

export const SCOPE_LABELS: Record<string, string> = {
  progress: "Progress summaries",
  mastery: "Topic levels",
  assessments: "Tests and marks",
  plans: "Study plans and schedule",
  conversations: "Tutor conversations",
  safety: "Safety alerts",
  memory: "Learning notes",
};
