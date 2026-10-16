const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export type ModuleId = "semestre" | "estudio" | "aprender" | "dinero" | "trayectoria" | "bandeja";
export type SubjectKind = "basica" | "obligatoria" | "optativa" | "mencion" | "practicas" | "tfg" | "otra";
export type SubjectStatus = "pending" | "enrolled" | "passed" | "failed" | "convalidated" | "dropped";
export type AiPolicy = "unknown" | "allowed" | "limited" | "forbidden";
export type EvalModel = "weighted" | "ec_pf";
export type ActivityKind = "pec" | "pr" | "quiz" | "video" | "exam" | "lab" | "project" | "other";
export type EventKind = "session" | "class" | "exam" | "admin" | "personal" | "other";
export type ExpenseCategory = "tuition" | "materials" | "books" | "exam" | "transport" | "software" | "other";
export type GrantStatus = "idea" | "preparing" | "applied" | "granted" | "rejected" | "paid";
export type ProcedureCategory = "enrollment" | "recognition" | "scholarship" | "internship" | "tfg" | "admin" | "other";
export type ProcedureStatus = "todo" | "doing" | "waiting" | "done";
export type PathKind = "course" | "certification" | "project" | "internship" | "job" | "language" | "volunteering" | "award" | "other";
export type PathStatus = "idea" | "planned" | "in_progress" | "done" | "dropped";

export type Settings = {
  modules: Record<ModuleId, boolean>;
  language: "es" | "en";
  default_price_per_credit: number;
  currency: string;
  heavy_week_subjects: number;
  obsidian_vault: string;
  learn_daily_xp: number;
  learn_sounds: boolean;
  notifications: { enabled: boolean; topic: string; hour: number; days_before: number[] };
};

export type Track = { id: string; name: string };
export type TermSystem = "semesters" | "trimesters" | "quarters" | "annual";
export type Offered = "both" | "s1" | "s2" | "t1" | "t2" | "t3" | "q1" | "q2" | "q3" | "q4";
export type CareerConfig = {
  grade_max: number;
  pass_mark: number;
  decimals: number;
  credit_label: string;
  term_system: TermSystem;
  year_start_month: number;
  labels: {
    subject_kinds: Partial<Record<SubjectKind, string>>;
    activity_kinds: Partial<Record<ActivityKind, string>>;
    ec: string;
    pf: string;
  };
  letters: GradeLetter[];
};
export type GradeLetter = { label: string; min: number; value: number };
export type Career = {
  id: number;
  name: string;
  institution: string;
  ects_goal: number;
  track: string | null;
  requirements: Record<string, number>;
  config: CareerConfig;
  archived: boolean;
  pack_slug: string | null;
  tracks: Track[];
};
export type CareerIn = Omit<Career, "id" | "pack_slug" | "tracks">;

export type CareerSummary = {
  career_id: number;
  ects_done: number;
  ects_enrolled: number;
  ects_goal: number;
  average: number | null;
  by_kind: Record<string, { done: number; enrolled: number; total: number }>;
  requirements: Record<string, number>;
  config: CareerConfig;
  subjects: number;
};

export type Term = { id: number; career_id: number; label: string; start_date: string; end_date: string | null };
export type TermIn = Omit<Term, "id">;

export type Link = { label: string; url: string };
export type Subject = {
  id: number;
  career_id: number;
  term_id: number | null;
  code: string;
  name: string;
  ects: number;
  kind: SubjectKind;
  plan_semester: number | null;
  offered: Offered | null;
  planned_term: string | null;
  track: string | null;
  status: SubjectStatus;
  final_grade: number | null;
  attempt: number;
  price_per_credit: number | null;
  weekly_hours: number | null;
  ai_policy: AiPolicy;
  ai_policy_note: string;
  eval_model: EvalModel;
  eval_config: { ec_pass: number; pf_min: number; no_show_grade: number };
  notes: string;
  links: Link[];
  pack_ref: string | null;
};
export type SubjectIn = Omit<Subject, "id" | "pack_ref">;

export type EvalGroup = {
  id: number;
  subject_id: number;
  name: string;
  weight: number;
  min_grade: number | null;
  role: "ec" | "pf" | null;
  position: number;
};
export type EvalGroupIn = Omit<EvalGroup, "id">;

export type Activity = {
  id: number;
  subject_id: number;
  group_id: number | null;
  name: string;
  kind: ActivityKind;
  weight: number;
  grade: number | null;
  max_grade: number;
  due_date: string | null;
  due_time: string | null;
  window_start: string | null;
  window_end: string | null;
  evaluable: boolean;
  done: boolean;
  kept_from_previous: boolean;
  estimated_hours: number | null;
  notes: string;
  pack_ref: string | null;
};
export type ActivityIn = Omit<Activity, "id" | "pack_ref">;

export type GroupResult = {
  id: number;
  name: string;
  weight: number;
  min_grade: number | null;
  grade: number | null;
  complete: boolean;
  pending: number;
  meets_min: boolean | null;
};
export type Evaluation = {
  groups: GroupResult[];
  current: number | null;
  final: number | null;
  passed: boolean | null;
  reasons: string[];
  pending: number;
  needed: number | null;
  achievable: boolean;
  official_grade: number | null;
  scale: number;
  pass_mark: number;
};

export type AgendaItem = {
  uid: string;
  type: "activity" | "window" | "event" | "procedure" | "grant";
  id: number;
  title: string;
  date: string;
  end_date: string | null;
  time: string | null;
  end_time: string | null;
  kind: string;
  subject_id: number | null;
  subject_name: string | null;
  done: boolean;
  evaluable: boolean;
  ai_forbidden: boolean;
  url: string;
};
export type HeavyWeek = { week: string; subjects: string[] };
export type Agenda = { start: string; end: string; items: AgendaItem[]; heavy_weeks: HeavyWeek[] };

export type CalEvent = {
  id: number;
  subject_id: number | null;
  title: string;
  kind: EventKind;
  date: string;
  end_date: string | null;
  start_time: string | null;
  end_time: string | null;
  url: string;
  notes: string;
  done: boolean;
};
export type CalEventIn = Omit<CalEvent, "id">;

export type Habit = { id: number; subject_id: number | null; title: string; weekdays: number[]; active: boolean };
export type HabitIn = Omit<Habit, "id">;

export type Dashboard = {
  today: string;
  upcoming: AgendaItem[];
  open_windows: AgendaItem[];
  overdue: { id: number; title: string; subject_id: number; date: string }[];
  heavy_weeks: HeavyWeek[];
  habits_today: { id: number; title: string; subject_id: number | null; done: boolean }[];
  study_minutes_week: number;
  cards_due: number;
  enrolled: { id: number; name: string; ects: number; ai_policy: AiPolicy; evaluation: Evaluation }[];
  careers: (CareerSummary & { name: string })[];
  today_plan: {
    kind: "deliver" | "study" | "review" | "lesson";
    title: string;
    detail: string;
    subject_id?: number;
    activity_id?: number;
    lesson_id?: number | null;
  }[];
  at_risk: { id: number; name: string; level: "crit" | "warn"; reason: string }[];
  week_load: { week: string; hours: number; deliveries: number }[];
  next_exam: AgendaItem | null;
  next_lessons: { subject_id: number; subject_name: string; lesson_id: number; title: string; done: number; total: number }[];
  learn: { streak: number; today_xp: number; goal: number };
  inbox_pending: { new: number; proposals: number } | null;
};

export type StudySession = { id: number; subject_id: number | null; date: string; minutes: number; kind: "focus" | "manual"; note: string };
export type StudySessionIn = Omit<StudySession, "id">;
export type StudyStats = {
  start: string;
  end: string;
  by_subject: { subject_id: number | null; subject_name: string; minutes: number; expected_minutes: number | null }[];
  daily: { date: string; minutes: number }[];
};

export type Card = {
  id: number;
  subject_id: number | null;
  deck: string;
  question: string;
  source: string;
  box: number;
  due_on: string;
  last_reviewed: string | null;
  reviews: number;
  lapses: number;
};

export type Expense = { id: number; subject_id: number | null; term_id: number | null; date: string; category: ExpenseCategory; description: string; amount: number };
export type ExpenseIn = Omit<Expense, "id">;
export type Grant = {
  id: number;
  name: string;
  provider: string;
  status: GrantStatus;
  amount: number | null;
  deadline: string | null;
  decision_date: string | null;
  min_average: number | null;
  income_threshold: number | null;
  url: string;
  notes: string;
};
export type GrantIn = Omit<Grant, "id">;
export type Procedure = {
  id: number;
  title: string;
  category: ProcedureCategory;
  status: ProcedureStatus;
  window_start: string | null;
  deadline: string | null;
  url: string;
  notes: string;
};
export type ProcedureIn = Omit<Procedure, "id">;
export type MoneySummary = {
  total: number;
  by_category: Record<string, number>;
  by_term: Record<string, number>;
  grants_total: number;
  currency: string;
};
export type TuitionEstimate = {
  term_id: number;
  label: string;
  rows: { subject_id: number; name: string; ects: number; attempt: number; price_per_credit: number; amount: number }[];
  total: number;
};

export type PathItem = {
  id: number;
  kind: PathKind;
  title: string;
  organization: string;
  status: PathStatus;
  start_date: string | null;
  end_date: string | null;
  hours: number | null;
  url: string;
  skills: string[];
  subject_id: number | null;
  notes: string;
};
export type PathItemIn = Omit<PathItem, "id">;

export type PackSummary = {
  slug: string;
  name: string;
  version: string;
  description: string;
  institution: string;
  degree: string;
  ects_total: number;
  credit_label?: string;
  source_url: string;
  updated: string | null;
  subjects: number;
  tracks: Track[];
  terms: { ref: string; label: string; subjects: number; applied: boolean }[];
  in_catalog: boolean;
  installed_version: string | null;
  career_id: number | null;
};

export type LessonSummary = {
  id: number;
  title: string;
  steps: number;
  done: boolean;
  best_ratio: number | null;
  has_theory: boolean;
  level: number;
  locked: boolean;
};
export type CourseSummary = {
  id: number;
  slug: string;
  title: string;
  description: string;
  source_note: string;
  subject_id: number | null;
  subject_name: string | null;
  lessons_total: number;
  lessons_done: number;
  next_lesson_id: number | null;
  units?: { id: number; title: string; done: boolean; chest_claimed: boolean; lessons: LessonSummary[] }[];
};
export type Figure = { svg: string; alt: string; caption: string };
export type PublicStep = {
  id: number;
  figure?: Figure;
  cite?: { material_id: number; page: number | null };
  kind: "info" | "choice" | "truefalse" | "numeric" | "complex" | "order" | "param" | "match";
  prompt: string;
  source: string;
  hints?: string[];
  concepts?: string[];
  worked?: string;
  token?: string;
  answer_kind?: "numeric" | "complex";
  options?: string[];
  multiple?: boolean;
  items?: string[];
  left?: string[];
  right?: string[];
  unit?: string;
  explanation?: string;
  lesson_title?: string;
};
export type LessonFull = {
  id: number;
  title: string;
  unit_title: string;
  course_id: number;
  course_title: string;
  theory: string;
  theory_url: string;
  done: boolean;
  next_lesson_id: number | null;
  steps: PublicStep[];
};
export type AnswerResult = {
  correct: boolean;
  solution: string;
  explanation: string;
  source: string;
  xp: number;
  option_feedback: string[];
  confident_wrong: boolean;
};
export type LearnStats = {
  today_xp: number;
  goal: number;
  streak: number;
  review_due: number;
  total_xp: number;
  confident_wrong: number;
  week: Record<string, number>;
};
export type Quest = { id: string; title: string; progress: number; target: number; gems: number; done: boolean; claimed: boolean };
export type GameState = {
  gems: number;
  streak_freezes: number;
  streak: number;
  today_xp: number;
  goal: number;
  week: { date: string; xp: number; frozen: boolean; future: boolean }[];
  quests: Quest[];
  prices: { freeze: number };
  max_freezes: number;
};
export type CompleteResult = {
  xp: number;
  perfect: boolean;
  ratio: number;
  level: number;
  streak: number;
  unit_done: boolean;
  unit_id: number;
  chest_available: boolean;
  game: GameState;
};
export type ConceptMastery = { concept: string; steps: number; correct: number; wrong: number; confident_wrong: number; due: number; mastery: number | null };
export type StepSet = { title: string; steps: PublicStep[]; minutes?: number };
export type AiProvider = "claude_code" | "anthropic" | "gemini" | "openrouter" | "ollama" | "openai_compatible";
export type AiStatus = { enabled: boolean; provider: AiProvider; source: "settings" | "server"; model: string; reason: string };
export type GeneratorStatus = AiStatus & { kinds: Record<string, string> };
export type AiProviderMeta = { label: string; needs_key: boolean; needs_url: boolean; default_url?: string; models: { generator: string; inbox: string } };
export type AiSettings = { provider: AiProvider | null; base_url: string; model_generator: string; model_inbox: string };
export type AiPublic = AiSettings & { has_key: boolean; status: AiStatus; providers: Record<AiProvider, AiProviderMeta> };
export type DraftStep = {
  ref: string;
  kind: PublicStep["kind"];
  prompt: string;
  source: string;
  explanation: string;
  hints: string[];
  concepts: string[];
  objectives?: string[];
  worked: string;
  data: Record<string, unknown>;
  flag?: string;
};

export type Material = {
  id: number;
  subject_id: number;
  module_ref: string;
  kind: string;
  filename: string;
  pages: number | null;
  has_file: boolean;
  chars: number;
  created_at: string;
};
export type TutorAnswer = {
  answer: string;
  in_material: boolean;
  citations: { material: string; section: string; page: number | null; material_id: number | null; has_file: boolean }[];
  materials: string[];
};

export type WeekModule = { ref: string; title: string; lessons: number; done: number; next_lesson_id: number | null; has_material: boolean };
export type StudyPlan = {
  subject_id: number;
  course_id: number | null;
  has_plan: boolean;
  weeks: { start: string; modules: string[] }[];
  current_week: number;
  this_week: WeekModule[];
  behind: WeekModule[];
  deadlines: { activity_id: number; name: string; kind: string; date: string; days: number }[];
  weak_objectives: { code: string; text: string; mastery: number }[];
  due_reviews: number;
  hours_goal: number | null;
  minutes_this_week: number;
};

export type CalendarFeed = {
  id: number;
  name: string;
  subject_id: number | null;
  mode: "events" | "activities";
  enabled: boolean;
  url_hint: string;
  items: number;
  last_error: string;
  last_sync: string | null;
};
export type CalendarFeedIn = { name: string; url: string; subject_id: number | null; mode: CalendarFeed["mode"]; enabled: boolean };

/** Módulo de estudios que sale de un plan de estudios (lo que importa para revisarlo). */
export type DegreePack = {
  slug: string;
  name: string;
  institution: string;
  degree: string;
  ects_total: number;
  requirements: Partial<Record<SubjectKind, number>>;
  config: { credit_label: string; grade_max?: number; pass_mark?: number } | null;
  tracks: { id: string; name: string }[];
  subjects: { ref: string; code?: string; name: string; ects: number; kind: SubjectKind; plan_semester?: number | null; track?: string | null }[];
};

export type ObjectiveKind = "general" | "conocimiento" | "habilidad" | "competencia";
export type PlanDraft = {
  summary: string;
  objectives: { code: string; kind: ObjectiveKind; text: string }[];
  modules: { ref: string; title: string; topics: string[]; objectives: string[] }[];
  resources: { title: string; kind: string }[];
  eval_model: EvalModel | null;
  ec_pass: number | null;
  pf_min: number | null;
  groups: { name: string; weight: number; min_grade: number | null; role: "ec" | "pf" | null }[];
  activities: { name: string; kind: string; group: string; weight: number; window_start: string | null; due_date: string | null; evaluable: boolean }[];
  ai_policy: AiPolicy;
  ai_policy_note: string;
};
export type SyllabusView = {
  subject_id: number;
  course_id: number | null;
  has_plan: boolean;
  summary: string;
  source: string;
  imported_on: string | null;
  objectives: { code: string; kind: ObjectiveKind; text: string; steps: number; correct: number; wrong: number; mastery: number | null; due: number }[];
  modules: { ref: string; title: string; topics: string[]; objectives: string[]; lessons: number; lessons_done: number }[];
  resources: { title: string; kind: string }[];
  unassigned_units: { id: number; title: string }[];
};
export type GenerationJob = {
  id: number;
  status: "queued" | "running" | "done" | "error";
  title: string;
  subject_id: number | null;
  material_kind: string;
  filenames: string[];
  created_at: string;
  finished_at: string | null;
  error: string;
  steps: number;
  review: number;
  dropped: number;
  cost_usd: number | null;
  mode: "lessons" | "theory" | "plan" | "career";
  plan_counts?: { objectives: number; modules: number; activities: number };
  subject_state?: { has_groups: boolean; has_plan: boolean; existing: boolean[] };
  draft?: { units: { ref: string; title: string; lessons: { ref: string; title: string; steps: DraftStep[] }[] }[]; refusal?: string | null; plan?: PlanDraft; pack?: DegreePack };
  warnings?: { step: string; lesson: string; level: "review" | "dropped"; message: string }[];
};

export class NetworkError extends Error {
  constructor() {
    super("Sin conexión con el servidor");
  }
}

export type InboxKind = "announcement" | "grade" | "video_check" | "forum" | "deadline" | "admin" | "other";
export type InboxProposal = {
  title: string;
  date: string;
  end_date: string | null;
  time: string | null;
  event_kind: EventKind;
  state: "pending" | "accepted" | "dismissed";
  event_id: number | null;
};
export type InboxMessage = {
  id: number;
  received_at: string;
  sender: string;
  title: string;
  body: string;
  status: "new" | "read" | "archived";
  subject_id: number | null;
  kind: InboxKind;
  summary: string;
  proposals: InboxProposal[];
  classify_status: "pending" | "running" | "done" | "error" | "off";
  classify_error: string;
};
export type InboxStats = { new: number; pending_proposals: number; ingest_configured: boolean };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { credentials: "same-origin", ...init });
  } catch {
    throw new NetworkError();
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    const message = Array.isArray(detail)
      ? detail.map((d: { msg?: string }) => (d.msg ?? "").replace(/^Value error, /, "")).join(" · ")
      : detail;
    throw new Error(message || `Error ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

const upload = (file: File, extra: Record<string, string> = {}): RequestInit => {
  const form = new FormData();
  form.append("file", file);
  for (const [k, v] of Object.entries(extra)) form.append(k, v);
  return { method: "POST", body: form };
};

const qs = (params: Record<string, string | number | null | undefined>) => {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  return entries.length ? `?${new URLSearchParams(entries.map(([k, v]) => [k, String(v)]))}` : "";
};

/** CRUD estándar de un recurso del backend (crud_router). */
function resource<T, TIn>(path: string) {
  return {
    list: (params: Record<string, string | number | null | undefined> = {}) => request<T[]>(`/${path}${qs(params)}`),
    get: (id: number) => request<T>(`/${path}/${id}`),
    create: (data: TIn) => request<T>(`/${path}`, json("POST", data)),
    update: (id: number, data: TIn) => request<T>(`/${path}/${id}`, json("PUT", data)),
    remove: (id: number) => request<void>(`/${path}/${id}`, { method: "DELETE" }),
  };
}

export const api = {
  inbox: {
    list: (status: "open" | "archived" = "open") => request<InboxMessage[]>(`/inbox${qs({ status })}`),
    stats: () => request<InboxStats>("/inbox/stats"),
    update: (id: number, data: { status?: InboxMessage["status"]; subject_id?: number; clear_subject?: boolean; kind?: InboxKind }) =>
      request<InboxMessage>(`/inbox/${id}`, json("PUT", data)),
    classify: (id: number) => request<InboxMessage>(`/inbox/${id}/classify`, { method: "POST" }),
    resolve: (id: number, index: number, action: "accept" | "dismiss") =>
      request<InboxMessage>(`/inbox/${id}/proposals/${index}`, json("POST", { action })),
    remove: (id: number) => request<void>(`/inbox/${id}`, { method: "DELETE" }),
  },
  settings: {
    get: () => request<Settings>("/settings"),
    save: (s: Settings) => request<Settings>("/settings", json("PUT", s)),
  },
  careers: resource<Career, CareerIn>("careers"),
  careerSummary: (id: number) => request<CareerSummary>(`/careers/${id}/summary`),
  exportPackUrl: (id: number) => `${API_BASE_URL}/careers/${id}/export-pack`,
  terms: resource<Term, TermIn>("terms"),
  subjects: resource<Subject, SubjectIn>("subjects"),
  groups: resource<EvalGroup, EvalGroupIn>("groups"),
  activities: resource<Activity, ActivityIn>("activities"),
  evaluation: (subjectId: number, target = 5) => request<Evaluation>(`/subjects/${subjectId}/evaluation${qs({ target })}`),
  simulate: (subjectId: number, hypothetical: Record<number, number>, target: number | null) =>
    request<Evaluation>(`/subjects/${subjectId}/simulate`, json("POST", { hypothetical, target })),
  evaluations: (params: { career_id?: number; term_id?: number }) => request<Record<string, Evaluation>>(`/evaluations${qs(params)}`),

  agenda: (start?: string, end?: string) => request<Agenda>(`/agenda${qs({ start, end })}`),
  events: resource<CalEvent, CalEventIn>("events"),
  habits: resource<Habit, HabitIn>("habits"),
  toggleHabit: (id: number, day?: string) => request<{ done: boolean }>(`/habits/${id}/check${qs({ day })}`, { method: "POST" }),
  habitsWeek: (start?: string) => request<{ start: string; checks: Record<string, string[]> }>(`/habits-week${qs({ start })}`),
  dashboard: () => request<Dashboard>("/dashboard"),
  calendarUrl: `${API_BASE_URL}/calendar.ics`,
  icalStatus: () => request<{ configured: boolean; path: string | null }>("/ical/status"),

  sessions: resource<StudySession, StudySessionIn>("sessions"),
  studyStats: (start?: string, end?: string) => request<StudyStats>(`/study/stats${qs({ start, end })}`),
  cards: resource<Card, { subject_id: number | null; deck: string; question: string; source: string }>("cards"),
  dueCards: (subject_id?: number) => request<Card[]>(`/cards-due${qs({ subject_id })}`),
  reviewCard: (id: number, knew: boolean) => request<Card>(`/cards/${id}/review`, json("POST", { knew })),
  importCards: (data: { subject_id: number | null; deck: string; source: string; markdown: string }) =>
    request<{ deck: string; found: number; added: number }>("/cards/import", json("POST", data)),

  expenses: resource<Expense, ExpenseIn>("expenses"),
  grants: resource<Grant, GrantIn>("grants"),
  procedures: resource<Procedure, ProcedureIn>("procedures"),
  moneySummary: () => request<MoneySummary>("/money/summary"),
  tuition: (termId: number) => request<TuitionEstimate>(`/terms/${termId}/tuition-estimate`),
  grantsEligibility: () => request<{ average: number | null; meets_min_average: Record<string, boolean | null> }>("/grants/eligibility"),

  path: resource<PathItem, PathItemIn>("path"),
  pathSkills: () => request<{ skill: string; count: number; done: number }[]>("/path-skills"),

  packs: {
    list: () => request<PackSummary[]>("/packs"),
    install: (slug: string) => request<{ slug: string; career_id: number }>(`/packs/${slug}/install`, { method: "POST" }),
    applyTerm: (slug: string, ref: string) =>
      request<{ term_id: number; subjects: number; activities: number; events: number; habits: number; procedures: number }>(
        `/packs/${slug}/terms/${ref}/apply`,
        { method: "POST" }
      ),
    upload: (file: File) => request<{ slug: string; career_id: number }>("/packs/upload", upload(file)),
    downloadUrl: (slug: string) => `${API_BASE_URL}/packs/${slug}/download`,
    uninstall: (slug: string, deleteCareer: boolean) =>
      request<void>(`/packs/${slug}${qs({ delete_career: deleteCareer ? "true" : undefined })}`, { method: "DELETE" }),
  },

  ai: {
    get: () => request<AiPublic>("/ai"),
    save: (body: AiSettings & { key?: string }) => request<AiPublic>("/ai", json("PUT", body)),
    removeKey: () => request<AiPublic>("/ai/key", { method: "DELETE" }),
    test: () => request<{ ok: boolean; provider: AiProvider; model: string }>("/ai/test", { method: "POST" }),
  },

  learn: {
    courses: () => request<CourseSummary[]>("/learn/courses"),
    course: (id: number) => request<CourseSummary>(`/learn/courses/${id}`),
    removeCourse: (id: number) => request<void>(`/learn/courses/${id}`, { method: "DELETE" }),
    exportUrl: (id: number) => `${API_BASE_URL}/learn/courses/${id}/export`,
    ankiUrl: (id: number, onlyMissed = false) => `${API_BASE_URL}/learn/courses/${id}/anki${onlyMissed ? "?only_missed=true" : ""}`,
    importCourse: (file: File, subjectId: number) => {
      const form = new FormData();
      form.append("file", file);
      form.append("subject_id", String(subjectId));
      return request<CourseSummary>("/learn/import", { method: "POST", body: form });
    },
    setCourseSubject: (courseId: number, subjectId: number) =>
      request<CourseSummary>(`/learn/courses/${courseId}/subject`, json("PUT", { subject_id: subjectId })),
    lesson: (id: number) => request<LessonFull>(`/learn/lessons/${id}`),
    saveTheory: (id: number, theory: string, theory_url: string) =>
      request<{ theory: string; theory_url: string }>(`/learn/lessons/${id}/theory`, json("PUT", { theory, theory_url })),
    answer: (
      stepId: number,
      response: unknown,
      opts: { firstTry: boolean; token?: string; confidence?: "high" | "low" | null; usedHint?: boolean; combo?: number }
    ) =>
      request<AnswerResult>(
        `/learn/steps/${stepId}/answer`,
        json("POST", {
          response,
          first_try: opts.firstTry,
          token: opts.token,
          confidence: opts.confidence ?? null,
          used_hint: !!opts.usedHint,
          combo: opts.combo ?? 0,
        })
      ),
    game: () => request<GameState>("/learn/game"),
    claimQuest: (id: string) => request<{ gems: number; game: GameState }>(`/learn/quests/${id}/claim`, { method: "POST" }),
    openChest: (unitId: number) => request<{ gems: number; game: GameState }>(`/learn/units/${unitId}/chest`, { method: "POST" }),
    buy: (item: "freeze") => request<GameState>(`/learn/shop/${item}`, { method: "POST" }),
    concepts: (courseId: number) => request<ConceptMastery[]>(`/learn/courses/${courseId}/concepts`),
    practice: (courseId: number, concept: string, objective = "") => request<StepSet>(`/learn/courses/${courseId}/practice${qs({ concept, objective })}`),
    exam: (courseId: number, n = 10, minutes = 30) => request<StepSet>(`/learn/courses/${courseId}/exam${qs({ n, minutes })}`),
    generatorStatus: () => request<GeneratorStatus>("/learn/generator/status"),
    generate: (files: File[], materialKind: string, title: string, subjectId: number, mode: "lessons" | "theory" = "lessons", moduleRef = "", materialIds: number[] = []) => {
      const form = new FormData();
      files.forEach((f) => form.append("files", f));
      materialIds.forEach((id) => form.append("material_ids", String(id)));
      form.append("material_kind", materialKind);
      form.append("title", title);
      form.append("subject_id", String(subjectId));
      form.append("mode", mode);
      form.append("module_ref", moduleRef);
      return request<GenerationJob>("/learn/generate", { method: "POST", body: form });
    },
    jobs: () => request<GenerationJob[]>("/learn/jobs"),
    job: (id: number) => request<GenerationJob>(`/learn/jobs/${id}`),
    removeJob: (id: number) => request<void>(`/learn/jobs/${id}`, { method: "DELETE" }),
    importJob: (id: number, body: { subject_id: number | null; exclude: string[]; use_eval?: boolean; activities?: number[] }) =>
      request<CourseSummary>(`/learn/jobs/${id}/import`, json("POST", body)),
    complete: (lessonId: number, correct: number, total: number, seconds = 0) =>
      request<CompleteResult>(`/learn/lessons/${lessonId}/complete`, json("POST", { correct, total, seconds })),
    review: () => request<{ steps: PublicStep[] }>("/learn/review"),
    stats: () => request<LearnStats>("/learn/stats"),
  },

  backupUrl: `${API_BASE_URL}/backup`,
  restoreBackup: (file: File) => request<{ status: string }>("/backup/restore", upload(file)),
  importIos: (careerId: number, file: File) =>
    request<{ added: number; updated: number; skipped: number }>("/import/ios", upload(file, { career_id: String(careerId) })),
  materials: {
    list: (subjectId: number) => request<Material[]>(`/materials${qs({ subject_id: subjectId })}`),
    upload: (subjectId: number, file: File, kind: string, moduleRef: string) => {
      const form = new FormData();
      form.append("file", file);
      form.append("subject_id", String(subjectId));
      form.append("kind", kind);
      form.append("module_ref", moduleRef);
      return request<Material>("/materials", { method: "POST", body: form });
    },
    setModule: (id: number, moduleRef: string) => request<Material>(`/materials/${id}`, json("PATCH", { module_ref: moduleRef })),
    remove: (id: number) => request<void>(`/materials/${id}`, { method: "DELETE" }),
    fileUrl: (id: number, page?: number | null) => `${API_BASE_URL}/materials/${id}/file${page ? `#page=${page}` : ""}`,
  },
  tutor: (body: { subject_id: number; question: string; history: { role: "user" | "tutor"; text: string }[]; module_ref?: string }) =>
    request<TutorAnswer>("/learn/tutor", json("POST", body)),
  calendarFeeds: {
    list: () => request<CalendarFeed[]>("/calendar-feeds"),
    create: (body: CalendarFeedIn) => request<CalendarFeed>("/calendar-feeds", json("POST", body)),
    sync: (id: number) => request<CalendarFeed>(`/calendar-feeds/${id}/sync`, { method: "POST" }),
    remove: (id: number) => request<void>(`/calendar-feeds/${id}`, { method: "DELETE" }),
  },
  degreePlan: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ id: number; status: string }>("/packs/from-plan", { method: "POST", body: form });
  },
  syllabus: {
    get: (subjectId: number) => request<SyllabusView>(`/subjects/${subjectId}/syllabus`),
    import: (subjectId: number, file: File) => {
      const form = new FormData();
      form.append("file", file);
      return request<{ id: number; status: string }>(`/subjects/${subjectId}/syllabus/import`, { method: "POST", body: form });
    },
    remove: (subjectId: number) => request<void>(`/subjects/${subjectId}/syllabus`, { method: "DELETE" }),
    studyPlan: (subjectId: number) => request<StudyPlan>(`/subjects/${subjectId}/study-plan`),
  },
  notifications: {
    status: () => request<{ configured: boolean; server: string | null }>("/notifications/status"),
    preview: () => request<{ lines: string[] }>("/notifications/preview"),
    test: () => request<{ status: string; topic: string }>("/notifications/test", { method: "POST" }),
  },
};
