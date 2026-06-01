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
  lecturer_ids?: string[];
  ta_ids?: string[];
}

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

export interface SolveResult {
  status: string;
  solved: boolean;
  feasible?: boolean;
  objective?: number;
  soft_penalty?: number;
  placements: Record<string, Placement>;
  violations: Violation[];
}
