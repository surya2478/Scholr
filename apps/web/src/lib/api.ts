// Typed client for the Scholr API (proxied at /api). Types mirror the FastAPI response schemas.

import { getToken } from "./session";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

export function getAuthHeader(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let body = init.body;
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  const res = await fetch(`/api${path}`, { ...init, headers, body, cache: "no-store" });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = (data as { error?: { code?: string; message?: string } }).error ?? {};
    throw new ApiError(res.status, err.code ?? "error", err.message ?? res.statusText);
  }
  return data as T;
}

// ---- identity ------------------------------------------------------------------------------------------------
export type Enrollment = {
  subject_id: string;
  subject_code: string;
  subject_name: string;
  tier: string | null;
  answer_input: "expression" | "text";
};
export type Me = {
  user: { id: string; display_name: string; role: "student" | "guardian" | "admin" };
  student: { id: string; display_name: string; year_group: string; timezone: string; enrollments: Enrollment[] } | null;
  guardian_visibility: { guardian_name: string; scopes: string[] }[];
  linked_students: { id: string; display_name: string; year_group: string; scopes: string[]; enrollments: Enrollment[] }[];
};

// ---- planner -------------------------------------------------------------------------------------------------
export type PlanItem = {
  id: string;
  position: number;
  subject_id: string;
  subject_name: string;
  objective_id: string | null;
  objective_code: string | null;
  objective_statement: string | null;
  kind: string;
  est_minutes: number;
  reason: string;
  status: "planned" | "in_progress" | "completed" | "skipped";
};
export type TimelineBlock = {
  kind: string;
  title: string;
  detail: string | null;
  minutes: number;
  start: string | null;
  end: string | null;
  status: PlanItem["status"] | null;
  plan_item_id: string | null;
};
export type Plan = {
  id: string;
  plan_date: string;
  capacity_minutes: number;
  planned_minutes: number;
  items: PlanItem[];
  timeline: TimelineBlock[];
  notices: string[];
};

// ---- progress ------------------------------------------------------------------------------------------------
export type SubjectProgress = {
  subject_id: string;
  subject_name: string;
  objectives_total: number;
  level_counts: Record<string, number>;
  competent_or_better: number;
  retention_high: number;
  open_mistakes: number;
  high_severity_mistakes: number;
};
export type ProgressSummary = {
  student_id: string;
  subjects: SubjectProgress[];
  week: {
    since: string;
    attempts_evaluated: number;
    answers_without_help: number;
    mistakes_fixed: number;
    study_minutes: number;
    active_days: number;
    plan_items_total: number;
    plan_items_completed: number;
    plan_items_skipped: number;
  };
  focus: { kind: "mistake" | "retention"; objective_code: string | null; label: string }[];
  recent_wins: { objective_code: string; objective_statement: string; level_name: string }[];
};
export type MetacognitionItem = {
  attempt_id: string;
  subject_id: string;
  question_stem: string;
  pre_confidence: number;
  confidence_label: string;
  marks_awarded: number;
  marks_available: number;
  percentage: number;
  quadrant: "true_mastery" | "dangerous_blindspot" | "hesitant_mastery" | "known_gap";
  mistakes: string[];
  submitted_at: string;
};
export type Metacognition = {
  student_id: string;
  total_evaluated_with_confidence: number;
  brier_calibration_score: number;
  calibration_rating: string;
  quadrants: {
    true_mastery: { count: number; percentage: number };
    dangerous_blindspot: { count: number; percentage: number };
    hesitant_mastery: { count: number; percentage: number };
    known_gap: { count: number; percentage: number };
  };
  blindspots: MetacognitionItem[];
  recent_items: MetacognitionItem[];
  advice: string;
  independence: {
    independence_index: number;
    tier: string;
    unassisted_count: number;
    nudged_count: number;
    assisted_count: number;
    total: number;
    advice: string;
  };
};
export type GuardianOverview = {
  student_id: string;
  student_name: string;
  scopes: string[];
  summary: ProgressSummary;
  evaluations_needing_review: number | null;
  upcoming_assessments: UpcomingBrief[] | null;
  safety: { open_total: number; open_by_severity: Record<string, number>; latest_open_at: string | null } | null;
  suggestions: { lead: string; text: string }[];
};
export type UpcomingBrief = {
  subject_id: string;
  subject_name: string;
  title: string;
  due_at: string;
  objectives_total: number;
  objectives_secure: number | null;
  notes: string | null;
};
export type Trends = {
  student_id: string;
  weeks: {
    week_start: string;
    topics_secure: number | null;
    answers_marked: number;
    without_help: number;
    with_hints: number;
    worked_solution: number;
    independent_share: number | null;
  }[];
  days: { day: string; study_minutes: number }[];
  subjects: { subject_id: string; subject_name: string; study_minutes: number }[];
  planned_minutes_per_day: number;
};

export type MonthTotals = { answers_marked: number; accuracy: number | null; active_days: number; study_minutes: number };
export type MonthlySummary = {
  student_id: string;
  student_name: string;
  month: string;
  previous_month: string;
  next_month: string | null;
  days_counted: number;
  totals: MonthTotals;
  previous: MonthTotals;
  subjects: {
    subject_id: string;
    subject_name: string;
    answers_marked: number;
    marks_awarded: number;
    marks_available: number;
    accuracy: number | null;
    independent_share: number | null;
    awaiting_review: number;
    sessions: number;
    study_minutes: number;
    mistakes_found: number;
    mistakes_resolved: number;
    topics_secured: number | null;
  }[];
  plan_items_total: number | null;
  plan_items_completed: number | null;
  plan_items_skipped: number | null;
  secured: { objective_code: string; objective_statement: string; level_name: string }[] | null;
  focus: { kind: "mistake" | "retention"; objective_code: string | null; label: string }[] | null;
};

// ---- mastery, mistakes, memory -------------------------------------------------------------------------------
export type Mastery = {
  objective_id: string;
  objective_code: string;
  objective_statement: string;
  subject_id: string;
  level: number;
  level_name: string;
  retention_risk: string;
  last_demonstrated_at: string | null;
};
export type Mistake = {
  id: string;
  subject_id: string;
  objective_id: string | null;
  objective_code: string | null;
  mistake_type: string;
  description: string;
  severity: "low" | "medium" | "high";
  occurrences: number;
  status: "open" | "improving" | "resolved";
  last_seen: string;
  resolution?: string | null;
};
export type AutopsyEntry = {
  evaluation_id: string;
  attempt_id: string;
  subject_id: string;
  objective_code: string | null;
  stem: string;
  category: string;
  takeaway: string;
  marks_awarded: number;
  marks_available: number;
  recorded_at: string;
};
export type Memory = { id: string; kind: string; statement: string; evidence_count: number; updated_at: string };

// ---- questions, attempts, evaluations ------------------------------------------------------------------------
export type Question = {
  id: string;
  subject_id: string;
  source_ref: string | null;
  context: string | null;
  stem: string;
  marks: number;
  command_word: string | null;
  has_diagram: boolean;
  calculator_allowed: boolean | null;
  objective_ids: string[];
};
export type Attempt = { id: string; status: string; evaluation_id: string | null };
export type Evaluation = {
  id: string;
  status: "final" | "needs_review" | "overridden";
  provisional: boolean;
  marks_awarded: number;
  marks_available: number;
  feedback: {
    summary: string;
    what_went_well: string | null;
    next_step: string;
    autopsy?: { category: string; takeaway: string; recorded_at: string } | null;
  };
  final_answer_check: { status: string; detail: string } | null;
  mistakes: { label: string; severity: string; description: string }[];
};
export type ExaminerInsight = {
  kind: "common_error" | "what_scored" | "advice";
  text: string;
  question_ref: string | null;
  component: string;
  exam_series: string;
  attribution: string;
};
export type ExaminerInsights = {
  item_ref: string | null;
  question: ExaminerInsight[];
  paper: ExaminerInsight[];
  note: string;
};
export type ReviewItem = {
  evaluation: Evaluation;
  source_ref: string | null;
  context: string | null;
  stem: string;
  working: string | null;
  final_answer: string | null;
  mark_scheme: string;
  confidence: number;
  issues: string[];
};

// ---- assessments ---------------------------------------------------------------------------------------------
export type AssessmentBrief = {
  id: string;
  subject_id: string;
  kind: string;
  form_code: string | null;
  status: string;
  total_marks: number;
  created_at: string;
  submitted_at: string | null;
};
export type Assessment = AssessmentBrief & {
  no_help: boolean;
  items: {
    position: number;
    question_item_id: string;
    marks: number;
    question: Question | null;
    attempt_id: string | null;
    evaluation_status: string | null;
    marks_awarded: number | null;
  }[];
  score: { awarded: number; available: number; answered: number; unmarked: number; pending_review: number; final: boolean } | null;
};

// ---- safety --------------------------------------------------------------------------------------------------
export type Incident = {
  id: string;
  occurred_at: string;
  category: string;
  severity: number;
  action_taken: string;
  escalation_status: string;
};

// ---- external training (IIT Foundation, Phase 3) ---------------------------------------------------------------
export type LessonRef = { objective_id: string; code: string; title: string };
export type ExternalTrainingLog = {
  id: string;
  subject_id: string;
  subject_name: string;
  kind: "class" | "test" | "homework" | "practice";
  title: string;
  occurred_on: string;
  duration_min: number | null;
  lessons: LessonRef[];
  weak_lessons: LessonRef[];
  score: number | null;
  max_score: number | null;
  questions_attempted: number | null;
  questions_missed: number | null;
  weaknesses: string[];
  notes: string | null;
};
export type Reinforcement = {
  objective_id: string;
  objective_code: string;
  objective_statement: string;
  subject_id: string;
  subject_name: string;
  concept: string;
  depth: number;
  practicable: boolean;
  reason: string;
  note: string | null;
  priority: number;
};
export type LessonStanding = {
  objective_id: string;
  code: string;
  title: string;
  sessions: number;
  last_seen_on: string;
  accuracy: number | null;
  flagged: boolean;
};
export type SubjectStanding = {
  subject_id: string;
  subject_name: string;
  sessions: number;
  minutes: number;
  last_seen_on: string | null;
  accuracy: number | null;
  lessons_covered: number;
  lessons_total: number;
  traceable: boolean;
  weak_lessons: LessonStanding[];
};
export type ExternalSummary = {
  subjects: SubjectStanding[];
  recent: ExternalTrainingLog[];
  reinforcement: Reinforcement[];
};

// Learn (docs/STUDENT-APP.md): streams → subjects → chapters → topics.
export type SubjectStage = "taught" | "lessons" | "planned" | "external";
export type SubjectCard = {
  id: string;
  code: string;
  name: string;
  syllabus_code: string | null;
  stage: SubjectStage;
  objectives: number;
  secure: number | null;
  practised: number;
};
export type Stream = {
  key: string;
  name: string;
  description: string;
  status: "open" | "later";
  subjects: SubjectCard[];
};
export type ObjectiveCard = {
  id: string;
  code: string;
  statement: string;
  mastery_level: number | null;
  mastery_name: string | null;
  items: number;
  lesson: "ready" | "not_enough_material" | "none";
  school_led: boolean;
  classes: number;
  struggled: boolean;
};
export type Chapter = { id: string; code: string; name: string; objectives: ObjectiveCard[]; chapters: Chapter[] };
export type SubjectLearn = { subject: SubjectCard; stream: string; chapters: Chapter[] };
export type SourceRef = { title: string; page: number | null };
export type Lesson = {
  id: string;
  status: "ready" | "not_enough_material";
  summary: string;
  sections: { heading: string; body: string; sources: SourceRef[] }[];
  key_terms: { term: string; meaning: string }[];
  worked_examples: {
    problem: string;
    steps: string[];
    final_answer: string;
    unit: string | null; // Physics: checked by Pint; blank when the answer has no unit
    checked: "sympy" | null;
    sources: SourceRef[];
    level: "basic" | "standard" | "exam" | null; // lesson v4: examples rise to exam standard
  }[];
  // Pictures the page draws for itself: `data` is what the API's check computed (AC-U14).
  diagrams: { kind: string; caption: string; data: Record<string, unknown>; sections: number[] }[];
  pitfalls: string[];
  generated_at: string;
  note: string;
};
// `label` is what the student sees ("June 2025 · Paper 21 · Q17(b)(ii)"); the API names it, not the UI.
export type ItemCard = {
  id: string;
  source_ref: string | null;
  label: string;
  marks: number;
  command_word: string | null;
  stem?: string | null;
  context?: string | null;
};
// The exam level of a topic (AC-U16): how the papers ask about it, counted from the bank, and one real past-paper
// question solved to full marks. The walkthrough's answer passed the check that marks hers, its marks are ones the
// official scheme awards, and a person approved it before it reached this page.
export type ExamLevel = {
  solves: boolean; // false for subjects where Scholr never writes an exam answer (Sociology)
  how_examined: {
    asked: number;
    marks_min: number;
    marks_max: number;
    papers: string[];
    years: string[];
    command_words: string[];
  } | null;
  worked: {
    item_id: string;
    label: string;
    context: string | null;
    stem: string;
    marks: number;
    has_diagram: boolean;
    steps: { text: string; mark: string }[];
    final_answer: string;
    tip: string | null;
  } | null;
  examiner: ExaminerInsights | null;
};
export type Topic = {
  objective: ObjectiveCard;
  subject: SubjectCard;
  path: string[];
  lesson: Lesson | null;
  lesson_available: boolean;
  tutor_available: boolean;
  check_yourself: ItemCard[];
  exam_questions: ItemCard[];
  exam_level: ExamLevel | null;
  crucible: Crucible | null;
  mistakes: { description: string; occurrences: number; status: string }[];
  connections: {
    objective_id: string;
    objective_code: string;
    statement: string;
    subject_name: string;
    concept: string;
    practicable: boolean;
  }[];
  external: ExternalLesson | null;
  // What this page is made of and how long it takes, computed from its own content (AC-U13).
  steps: { key: string; label: string; minutes: number; done: boolean }[];
  minutes: number;
  notice: string | null;
};
export type ExternalLesson = {
  classes: {
    occurred_on: string;
    kind: string;
    title: string;
    score: number | null;
    max_score: number | null;
    struggled: boolean;
  }[];
  ground: {
    objective_id: string;
    objective_code: string;
    statement: string;
    subject_name: string;
    concept: string;
    depth: number;
    practicable: boolean;
    reason: string;
  }[];
  warm_up: ItemCard[];
};

// Daily practice set and past-paper hub (docs/STUDENT-APP.md step 4).
export type DailyItem = {
  item_id: string;
  subject_id: string;
  subject_name: string;
  objective_id: string;
  objective_code: string;
  objective_statement: string;
  source_ref: string | null;
  label: string;
  marks: number;
  reason_code: string;
  reason: string;
  status: "to_do" | "answered" | "marked" | "provisional";
  evaluation_id: string | null;
  marks_awarded: number | null;
};
export type DailyPractice = {
  practice_date: string;
  rule_version: string;
  items: DailyItem[];
  done: number;
  total: number;
  notice: string | null;
};
export type PastPaperItem = {
  id: string;
  source_ref: string | null;
  series: string | null;
  paper: string | null;
  question: string | null;
  marks: number;
  command_word: string | null;
  last_status: "marked" | "provisional" | "answered" | null;
  last_marks: number | null;
};
export type PastPapers = {
  subject: SubjectCard;
  chapters: { id: string | null; code: string; name: string; items: PastPaperItem[] }[];
  series: string[];
  total: number;
  attempted: number;
};

// Timed past-paper sittings (Phase 2 AC-R3): a whole paper under its real time limit, no help until submitted.
export type PaperToSit = {
  paper_ref: string;
  component_code: string | null;
  label: string;
  questions: number;
  bank_marks: number;
  paper_marks: number | null;
  duration_min: number | null;
  sat_on: string | null;
  assessment_id: string | null;
  question_numbers: string[];
  compulsory: string[];
  choose_from: string[];
  choose_count: number;
  in_progress: boolean;
};
export type Sitting = {
  assessment_id: string;
  paper_ref: string;
  label: string;
  questions: string[];
  items: number;
  marks: number;
  duration_min: number | null;
  minutes_left: number | null;
  over_time: boolean;
  status: string;
};

// ---- cognitive mutation & bug-hunting (Innovation 3) ---------------------------------------------------------
// Bug Hunter (mistakes/challenges.py): a candidate's working on a real past-paper question, built from an approved
// walkthrough with one SymPy-checked slip. The page is never told which step is wrong; the verdict says.
export type BugChallenge = {
  id: string;
  title: string;
  topic_name: string;
  label: string;
  question_context: string | null;
  question_stem: string;
  marks_available: number;
  student_steps: { step_number: number; text: string }[];
  final_answer: string;
};
export type BugVerificationOut = {
  correct_step: boolean;
  correct_type: boolean;
  correct_mark: boolean; // her decision on the step's mark matched the scheme's convention
  success: boolean;
  score: number;
  bug_step: number;
  bug_explanation: string;
  correct_text: string;
  examiner_report: string;
  official_mark: string;
  examiner: ExaminerInsights | null;
};

// The Crucible (learn/crucible.py): perspectives on a real essay question, cited from her coursebook, approved by a
// person. Part of the topic page (Topic.crucible); she writes her own answer to the question the normal way.
export type Crucible = {
  question: ItemCard;
  stem: string;
  perspectives: {
    perspective: string;
    sociologist: string;
    argument: string;
    key_concept: string;
    evidence: string;
    sources: SourceRef[];
  }[];
  questions: string[];
};

// The viva (docs/STUDENT-APP.md §19): defend each step of an approved solved exam question.
export type VivaTopic = {
  objective_id: string;
  code: string;
  statement: string;
  label: string;
  marks: number;
  steps: number;
};
export type VivaQuestion = VivaTopic & { context: string | null; stem: string; has_diagram: boolean };
export type VivaStep = {
  verdict: "right" | "partly" | "not_yet" | "safety";
  what_was_right: string;
  missing: string;
  hint: string;
  step_text: string;
  step_mark: string;
  last: boolean;
  safety_message: string | null;
};
