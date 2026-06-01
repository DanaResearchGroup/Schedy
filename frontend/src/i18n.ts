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
  number: { he: "מספר קורס", en: "Course number" },
  empty: { he: "לא נמצאה מערכת — הוסף קורסים ולחץ פתור", en: "No schedule yet — add courses and Solve" },
} as const;

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
