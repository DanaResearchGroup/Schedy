// Minimal bilingual strings + RTL handling. Hebrew is the primary planner
// language; English is the fallback. Switching to Hebrew flips the document to RTL.

export type Lang = "he" | "en";

export const STRINGS = {
  title: { he: "סקדי — מערכת שיבוץ", en: "Schedy — Department Scheduler" },
  catalog: { he: "קטלוג קורסים", en: "Course catalog" },
  solve: { he: "פתור", en: "Solve" },
  solving: { he: "פותר…", en: "Solving…" },
  schedule: { he: "מערכת שעות", en: "Weekly schedule" },
  violations: { he: "התנגשויות", en: "Violations" },
  exportCsv: { he: "ייצוא CSV", en: "Export CSV" },
  exportPdf: { he: "ייצוא PDF", en: "Export PDF" },
  noViolations: { he: "אין התנגשויות קשות", en: "No hard violations" },
  feasible: { he: "תקין", en: "Feasible" },
  infeasible: { he: "לא תקין", en: "Has hard conflicts" },
  addCourse: { he: "הוסף קורס", en: "Add course" },
  editCourse: { he: "עריכת קורס", en: "Edit course" },
  newCourse: { he: "קורס חדש", en: "New course" },
  number: { he: "מספר קורס", en: "Course number" },
  empty: { he: "לא נמצאה מערכת — הוסף קורסים ולחץ פתור", en: "No schedule yet — add courses and Solve" },
  save: { he: "שמור", en: "Save" },
  cancel: { he: "ביטול", en: "Cancel" },
  nameHe: { he: "שם בעברית", en: "Hebrew name" },
  nameEn: { he: "שם באנגלית", en: "English name" },
  programs: { he: "תוכניות", en: "Programs" },
  year: { he: "שנה", en: "Year" },
  role: { he: "סוג", en: "Role" },
  sessions: { he: "מבנה הקורס", en: "Session structure" },
  lectureHours: { he: "שעות הרצאה", en: "Lecture hours" },
  exerciseGroups: { he: "קבוצות תרגול", en: "Exercise groups" },
  exerciseHours: { he: "שעות תרגול", en: "Exercise hours" },
  labHours: { he: "שעות מעבדה", en: "Lab hours" },
  labDays: { he: "ימי מעבדה", en: "Lab days" },
  enrollment: { he: "מספר נרשמים צפוי", en: "Expected enrollment" },
  computerFarm: { he: "דורש חוות מחשבים", en: "Needs computer farm" },
  remote: { he: "מקוון (זום)", en: "Remote (Zoom)" },
  external: { he: "קורס חיצוני (קבוע)", en: "External course (fixed)" },
  placement: { he: "מיקום קבוע", en: "Fixed placement" },
  from: { he: "משעה", en: "From" },
  to: { he: "עד שעה", en: "To" },
  room: { he: "חדר", en: "Room" },
  lecturers: { he: "מרצים (מופרד בפסיק)", en: "Lecturers (comma-separated)" },
  tas: { he: "מתרגלים (מופרד בפסיק)", en: "TAs (comma-separated)" },
  required: { he: "נדרש מספר קורס", en: "Course number is required" },
} as const;

export const ROLE_LABEL: Record<string, Record<Lang, string>> = {
  core: { he: "ליבה", en: "core" },
  elective: { he: "בחירה", en: "elective" },
  replacement: { he: "חלופי", en: "replacement" },
  lab: { he: "מעבדה", en: "lab" },
};

export const DAY_NAMES: Record<Lang, string[]> = {
  en: ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"],
  he: ["ראשון", "שני", "שלישי", "רביעי", "חמישי"],
};

export function boxLabel(box: number): string {
  const start = 8 * 60 + 30 + box * 60;
  const end = start + 60;
  const fmt = (m: number) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
  return `${fmt(start)}-${fmt(end)}`;
}

export const t = (key: keyof typeof STRINGS, lang: Lang): string => STRINGS[key][lang];

export function minutesToHHMM(m: number | null | undefined): string {
  if (m == null) return "";
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

export function hhmmToMinutes(s: string): number | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec(s.trim());
  if (!m) return null;
  return parseInt(m[1], 10) * 60 + parseInt(m[2], 10);
}
