// Mirrors the backend's JSON shapes.

export type Program = "ChemE" | "BioChemE" | "ChemE-Chemistry";
export type Role = "core" | "elective" | "replacement" | "lab";

// An academic year plus a semester — the unit everything else is scoped by.
export type Semester = "winter" | "spring";

const SEMESTER_WORDS: Record<Semester, string[]> = {
  winter: ["winter", "חורף"],
  spring: ["spring", "אביב"],
};

/**
 * Read a typed semester, or null if it isn't one.
 *
 * Null rather than a default, because everything in the app is scoped to a
 * term: a misread semester doesn't fail, it quietly files a year's work under
 * the wrong half of the year. An abbreviation is accepted only while it can
 * still mean one semester — "spr" is spring, "sprng" is nothing.
 */
export function parseSemester(raw: string): Semester | null {
  const s = raw.trim().toLowerCase();
  if (!s) return null;
  const hits = (Object.keys(SEMESTER_WORDS) as Semester[])
    .filter((k) => SEMESTER_WORDS[k].some((w) => w.startsWith(s)));
  return hits.length === 1 ? hits[0] : null;
}

export interface Term {
  id: string;        // "2026-27-winter"
  year: string;      // "2026-27"
  semester: Semester;
  created: string;
  published: string | null;
}

export interface TermList {
  terms: Term[];
  current: string;
  // Set only on a database migrated from before terms existed: the name was
  // guessed and the planner still has to confirm it.
  needs_naming: string | null;
}

export interface Course {
  number: string;
  name_he?: string;
  name_en?: string;
  programs: Program[];
  year: number;
  role: Role;
  lecture_boxes?: number;
  num_exercise_groups?: number;
  exercise_boxes?: number;
  lab_boxes?: number;
  lab_days?: number[];
  expected_enrollment?: number;
  needs_computer_farm?: boolean;
  is_remote?: boolean;
  is_external?: boolean;
  ext_day?: number | null;
  ext_start_min?: number | null;
  ext_end_min?: number | null;
  ext_room?: string | null;
  lecturer_ids?: string[];
  ta_ids?: string[];
  // Sitting out this semester? Absent means offered (older catalogs).
  offered?: boolean;
  skip_reason?: string;
  // Academic credit points (e.g. 2.5). Absent for pre-existing catalogs.
  credit?: number | null;
  // Who may take it. Null/absent means "derive from the number".
  level?: CourseLevel | null;
  cadence?: Cadence;
  // A rolled-over graduate course standing in for one not yet confirmed.
  provisional?: boolean;
}

export type CourseLevel = "ug" | "joint" | "grad";
export type Cadence = "annual" | "biennial";

// Mirrors `catalog.suggest_level`: our numbering says who a course is for, and
// anything else belongs to another faculty where no convention holds.
const LEVEL_PREFIXES: Record<string, CourseLevel> = {
  "0054": "ug", "0056": "joint", "0058": "grad",
};

export function suggestLevel(number: string): CourseLevel {
  return LEVEL_PREFIXES[number.trim().slice(0, 4)] ?? "ug";
}

export const effectiveLevel = (c: Course): CourseLevel =>
  c.level ?? suggestLevel(c.number);

export interface RolloverCourse extends Course {
  last_run: string;   // the term it was last taught in
  due: boolean;       // its cadence says it should run this term
}

export const ROOMS: { id: string; name: string; capacity: number; farm?: boolean }[] = [
  { id: "hall1", name: "Hall 1 (210)", capacity: 210 },
  { id: "room2", name: "Classroom 2 — computer farm (22)", capacity: 22, farm: true },
  { id: "room3", name: "Classroom 3 (50)", capacity: 50 },
  { id: "room4", name: "Classroom 4 (50)", capacity: 50 },
  { id: "room5", name: "Classroom 5 (50)", capacity: 50 },
  { id: "hall6", name: "Hall 6 (120)", capacity: 120 },
];

export const PROGRAMS: Program[] = ["ChemE", "BioChemE", "ChemE-Chemistry"];
export const ROLES: Role[] = ["core", "elective", "replacement", "lab"];

export interface Placement {
  day: number;
  start_box: number;
  room_id: string;
}

export interface Violation {
  kind: string;
  severity: "hard" | "soft";
  message: string;
  session_ids: string[];
  weight: number;
}

export interface SessionMeta {
  course_number: string;
  type: "lecture" | "exercise" | "lab";
  group: string | null;
  length_boxes: number;
  role: Role;
  cohorts: string[];
  lecturers: string[];
  tas: string[];
  is_remote: boolean;
  fixed: boolean;
  // Frozen by publication — already handed to students, so it cannot be dragged.
  published?: boolean;
  // A stand-in for a course not yet confirmed: it holds hours through phase 1.
  provisional?: boolean;
  // Who may take it — drives the hard graduate non-overlap rule.
  level?: CourseLevel;
  enrollment: number;
  needs_farm: boolean;
  lab_group: string | null;
}

export interface SolveResult {
  status: string;
  solved: boolean;
  feasible?: boolean;
  objective?: number;
  soft_penalty?: number;
  placements: Record<string, Placement>;
  sessions: Record<string, SessionMeta>;
  violations: Violation[];
  // Published sessions the catalog no longer produces — they have dropped out
  // of a frozen schedule without breaking any rule.
  published_missing?: string[];
  // Published sessions the re-imported university skeleton now wants elsewhere.
  published_conflicts?: PublishedConflict[];
}

export interface PublishedConflict {
  session_id: string;
  published: [number, number];   // day, start box
  skeleton: [number, number];
}

// person id -> list of [day, box] cells the person is NOT available to teach.
export type Availability = Record<string, [number, number][]>;

export interface FixedEvent {
  id: string;
  label: string;
  day: number;
  start_box: number;
  length_boxes: number;
  kind: "blackout" | "external";
  cohorts: string[];
  // Another faculty's graduate course owns no cohort of ours, so only its level
  // ties it to our graduate courses. Null for a blackout, which has no course.
  level?: CourseLevel | null;
}

export interface SemesterCalendar {
  start: string; // ISO date (YYYY-MM-DD)
  end: string; // ISO date, inclusive
  blocked_dates: string[];
  substitutions: Record<string, number>; // ISO date -> weekday template 0..4
}

export interface LostSession {
  session_id: string;
  course_number: string;
  weekday_template: number;
  realized: number;
  baseline: number;
  deficit: number;
}

// Why an exercise meets before its lecture. "template_order" repeats every week
// (the fix is to move a session); "substitution" is one week a day-swap flipped.
export type InversionCause = "template_order" | "substitution";

export interface OrderInversion {
  course_number: string;
  week_index: number; // first realized week affected
  lecture_date: string;
  exercise_date: string;
  exercise_group: string | null;
  cause: InversionCause;
  weeks: number; // how many realized weeks this same inversion hits
  // Academic-hour boxes. The dates are equal when both sit on the same weekday,
  // and then only these tell the pair apart.
  lecture_box: number;
  exercise_box: number;
}

export interface CalendarAnalysis {
  total_days: number;
  teaching_days: number;
  weeks: number;
  week_anchor: number; // weekday (0..4) the teaching week starts on

  template_counts: Record<string, number>;
  substituted_days: { date: string; template: number | null }[];
  blocked_count: number;
  lost_sessions: LostSession[];
  order_inversions: OrderInversion[];
}

export interface CourseOfInterest {
  number: string;
  name: string;
}

export type PersonKind = "faculty" | "grad";

export interface Person {
  id: string;
  name: string;
  kind: PersonKind;
}

export interface SavedMeta {
  id: string;
  name: string;
  created_at: string; // ISO timestamp
  stats: { sessions?: number; hard?: number; soft_penalty?: number };
  note: string | null;
  // Which term it came from. Null for saves written before terms existed.
  term?: string | null;
}

export interface DiffChange {
  session_id: string;
  course_number: string;
  name: string;
  type: string;
  group: string | null;
  a: Placement | null;
  b: Placement | null;
  status: "moved" | "added" | "removed";
}

export interface ScheduleDiff {
  a: { id: string; name: string; stats: SavedMeta["stats"] };
  b: { id: string; name: string; stats: SavedMeta["stats"] };
  summary: { moved: number; added: number; removed: number; unchanged: number };
  changes: DiffChange[];
}

export interface OfferedRow {
  course_number: string;
  event_type: string | null;
  group_code: string | null;
  name_he: string;
  name_en: string;
  day: number | null;
  start_min: number | null;
  end_min: number | null;
  room: string;
  package: string;
  row: number;
  pinned?: boolean;
  faculty?: string;
  language?: string;
  person?: string;
  // Every other named column of the skeleton, slug -> text, in display order.
  // Blank cells are absent, so a missing key just means the export said nothing.
  details?: Record<string, string>;
}
