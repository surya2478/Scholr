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
  stage: SubjectStage;
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
  // A topic with questions she has not answered one of today: Done waits for an answer.
  needs_answer: boolean;
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
  focus: {
    kind: "mistake" | "retention";
    subject_id: string;
    objective_id: string | null;
    objective_code: string | null;
    label: string;
  }[];
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
  time_spent_s?: number | null;
  velocity_category?: "optimal_flow" | "speed_trap" | "time_sink" | "hesitant_success" | "untracked";
};
export type VelocityQuadrant = {
  count: number;
  percentage: number;
};
export type VelocityStats = {
  speed_trap_count: number;
  time_sink_count: number;
  optimal_flow_count: number;
  hesitant_count: number;
  average_seconds_per_mark: number;
  exam_time_used_percent: number | null;
  quadrants: {
    optimal_flow: VelocityQuadrant;
    speed_trap: VelocityQuadrant;
    time_sink: VelocityQuadrant;
    hesitant_success: VelocityQuadrant;
  };
  diagnosis: string;
};
export type Metacognition = {
  student_id: string;
  total_evaluated_with_confidence: number;
  brier_calibration_score: number | null;
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
  velocity?: VelocityStats | null;
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
// A recurring fixed commitment (a coaching class, sport, school hours). Her own record: `GET /commitments`.
export type Commitment = {
  id: string;
  kind: string;
  title: string;
  rrule: string;
  start_time: string | null;
  duration_min: number;
  notes: string | null;
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
  // null for her while the mark is provisional (AC-E6): `pending` says what her answer did instead.
  marks_awarded: number | null;
  marks_available: number;
  pending?: {
    points_made: string[];
    points_missed: string[];
    who: string;
    waiting_since: string;
  } | null;
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
// A topic exam's settings; past papers and study tests carry only total_marks and objective_ids.
export type AssessmentConfig = {
  title?: string;
  exam_category?: ExamCategory;
  duration_min?: number;
  target_marks?: number;
  total_marks?: number;
  objective_ids?: string[];
};
export type AssessmentBrief = {
  id: string;
  subject_id: string;
  kind: string;
  form_code: string | null;
  status: string;
  total_marks: number;
  created_at: string;
  submitted_at: string | null;
  config?: AssessmentConfig | null;
};
export type Assessment = AssessmentBrief & {
  no_help: boolean;
  started_at: string | null;
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

export type ObjectiveNode = {
  id: string;
  code: string;
  statement: string;
  tier: string;
  verification_status: string;
};

export type TopicNode = {
  id: string;
  code: string;
  name: string;
  depth: number;
  verification_status: string;
  objectives: ObjectiveNode[];
  children: TopicNode[];
};

export type SubjectTree = {
  subject: {
    id: string;
    code: string;
    name: string;
    syllabus_code: string | null;
    syllabus_title: string | null;
    stage: string;
    taught_here: boolean;
  };
  topics: TopicNode[];
};

export type ExamCategory = "practice_exam" | "pre_term" | "term" | "mid_term" | "final";

export type Bookmark = {
  question_item_id: string;
  subject_id: string;
  source_ref: string | null;
  stem: string;
  marks: number;
  tag: BookmarkTag;
  note: string | null;
  saved_at: string;
};
export type BookmarkTag = "examiner_trap" | "calc_heavy" | "must_revise";
export type CommandWords = { source: string | null; definitions: Record<string, string> };

export type ExamFromTopicsIn = {
  subject_id: string;
  title: string;
  exam_category: ExamCategory;
  objective_ids: string[];
  target_marks?: number;
  duration_minutes?: number;
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
  introduction: string; // lesson v5; empty before
  podcast_audio_url?: string | null;
  podcast_script?: { speaker: string; text: string }[];
  // v5 sections are revision notes: a definition, bullet points and an exam tip (body = the points joined, for
  // the voice). Older sections have prose in `body` only.
  sections: {
    heading: string;
    body: string;
    definition: string;
    points: string[];
    exam_tip: string;
    mental_model?: string;
    formula_notes?: string;
    sources: SourceRef[];
  }[];
  // Every number in a table is in the pages it cites; `section` (from 1) is where it goes, 0 = after the sections.
  tables: { title: string; columns: string[]; rows: string[][]; section: number; sources: SourceRef[] }[];
  exam_answers: { question: string; points: string[]; sources: SourceRef[] }[];
  key_terms: { term: string; meaning: string }[];
  worked_examples: {
    problem: string;
    strategy?: string; // coaching game plan ("How to Think")
    steps: string[];
    final_answer: string;
    unit: string | null; // Physics: checked by Pint; blank when the answer has no unit
    checked: "sympy" | null;
    coaching_takeaway?: string; // trap warning / takeaway
    sources: SourceRef[];
    level: "basic" | "standard" | "exam" | null; // lesson v4: examples rise to exam standard
    section: number; // lesson v5: the section it follows (from 1); 0 = after the sections
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
  difficulty?: number | null;
  origin?: string | null;
  last_status?: "answered" | "provisional" | "marked" | null;
  last_marks?: number | null;
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
  // "questions" once she has read the topic: she answers from memory before she re-reads.
  opens_on: "notes" | "questions";
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
// A topic tomorrow's set would start from. Served only once today's set is finished, and it can change: tomorrow's
// plan is built in the morning, and anything she does between now and then changes what is waiting.
export type TomorrowTopic = {
  subject_id: string;
  subject_name: string;
  objective_id: string;
  objective_code: string;
  objective_statement: string;
  reason_code: string;
  reason: string;
};
// A topic her homework photo looks like. No book text comes with it: she is offered a topic, never an excerpt.
export type HomeworkMatch = {
  objective_id: string;
  code: string;
  statement: string;
  subject_id: string;
  subject_name: string;
  similarity: number;
};
export type HomeworkPhoto = {
  read: boolean;
  text_preview: string;
  state: "HIGH" | "MEDIUM" | "LOW" | "NONE";
  matches: HomeworkMatch[];
  notice: string | null;
};
// One way into today's work. `minutes` is what the door's own content takes — about a minute a mark for
// questions, the topic page's own estimate for "deep" — not the size the door aims at. A closed door says why.
export type SessionDoor = {
  key: "quick" | "today" | "deep";
  text: string;
  minutes: number;
  questions: number;
  objective_id: string | null;
  objective_code: string | null;
  objective_statement: string | null;
  parts: string[];
  open: boolean;
  closed_reason: string | null;
};
export type DailyPractice = {
  practice_date: string;
  rule_version: string;
  items: DailyItem[];
  done: number;
  total: number;
  notice: string | null;
  answering_minutes: number;
  planned_minutes: number | null;
  external_minutes: number;
  tomorrow: TomorrowTopic[];
  doors: SessionDoor[];
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

// Digital Notebooks (Quizrr-inspired)
export type Notebook = {
  id: string;
  student_id: string;
  title: string;
  description: string | null;
  icon: string;
  color: string;
  subject_id: string | null;
  item_count: number;
  created_at: string;
  updated_at: string;
};

export type NotebookItem = {
  id: string;
  notebook_id: string;
  question_item_id: string;
  student_notes: string | null;
  created_at: string;
  question?: Question | null;
};

// Assessment Performance Diagnostic Report (15-Page In-Depth Analytics)
export type TimeSinkItem = {
  position: number;
  question_id: string;
  stem_snippet: string;
  marks_available: number;
  marks_awarded: number;
  time_spent_s: number;
  pace_seconds_per_mark: number;
};

export type TopicBreakdownItem = {
  topic_id: string;
  code: string;
  title: string;
  marks_available: number;
  marks_awarded: number;
  accuracy_pct: number;
  status: "mastered" | "solid" | "needs_work";
};

export type DifficultyBreakdownItem = {
  tier: number;
  label: string;
  marks_available: number;
  marks_awarded: number;
  accuracy_pct: number;
};

export type PacingSummary = {
  total_time_seconds: number;
  avg_time_per_question_s: number;
  avg_time_per_mark_s: number;
  target_pace_s_per_mark: number;
  pace_status: "optimal" | "rushed" | "slow";
};

export type AssessmentReport = {
  assessment_id: string;
  title: string;
  kind: string;
  total_questions: number;
  total_marks_available: number;
  total_marks_awarded: number;
  score_percentage: number;
  pacing: PacingSummary;
  time_sinks: TimeSinkItem[];
  topic_breakdown: TopicBreakdownItem[];
  difficulty_breakdown: DifficultyBreakdownItem[];
  mistake_types_summary: Record<string, number>;
  action_plan: string[];
};

