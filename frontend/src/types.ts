// Mirrors the backend's JSON shapes.

export type Program = "ChemE" | "BioChemE" | "ChemE-Chemistry";
export type Role = "core" | "elective" | "replacement" | "lab";

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
}

export const ROOMS: { id: string; name: string }[] = [
  { id: "hall1", name: "Hall 1 (210)" },
  { id: "room2", name: "Classroom 2 — computer farm (22)" },
  { id: "room3", name: "Classroom 3 (50)" },
  { id: "room4", name: "Classroom 4 (50)" },
  { id: "room5", name: "Classroom 5 (50)" },
  { id: "hall6", name: "Hall 6 (120)" },
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
}

// person id -> list of [day, box] cells the person is NOT available to teach.
export type Availability = Record<string, [number, number][]>;

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

export interface OrderInversion {
  course_number: string;
  week_index: number;
  lecture_date: string;
  exercise_date: string;
  exercise_group: string | null;
}

export interface CalendarAnalysis {
  total_days: number;
  teaching_days: number;
  weeks: number;
  template_counts: Record<string, number>;
  substituted_days: { date: string; template: number | null }[];
  blocked_count: number;
  lost_sessions: LostSession[];
  order_inversions: OrderInversion[];
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
}
