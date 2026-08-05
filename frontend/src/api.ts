import type {
  Availability,
  CalendarAnalysis,
  Course,
  CourseOfInterest,
  FixedEvent,
  OfferedRow,
  Person,
  Placement,
  RolloverCourse,
  SavedMeta,
  ScheduleDiff,
  SemesterCalendar,
  Semester,
  SessionMeta,
  SolveResult,
  Term,
  TermList,
  Violation,
} from "./types";

export interface Config {
  /** The folder saved schedules are read from and written to. */
  saves_dir: string;
  /** The folder saves must sit under — set at install time, not from here. */
  saves_root: string;
  /** A stored folder that fell outside the root and had to be refused. */
  rejected_saves_dir: string | null;
}

export interface EvalResult {
  feasible: boolean;
  soft_penalty: number;
  sessions: Record<string, SessionMeta>;
  violations: Violation[];
}

export interface UploadResult {
  count: number;
  offered: OfferedRow[];
  // "no_courses_of_interest": the file parsed, but nothing says which courses we
  // care about, so nothing was kept. Not an error — the list just isn't loaded.
  warning?: string;
}

// Dev: "/api" (Vite proxies it to the backend, stripping the prefix).
// Production build: VITE_API_BASE="" so calls hit the same FastAPI origin that
// serves the built SPA (see frontend/.env.production and docs/windows.md).
const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => fetch(`${BASE}/health`).then(json<{ status: string; courses: number }>),

  // Wipes the catalog and every setting. The server demands confirm=true so a
  // stray call can't empty the database.
  reset: () =>
    fetch(`${BASE}/reset?confirm=true`, { method: "POST" }).then(
      json<{ reset: boolean; courses: number; settings: number }>,
    ),

  // Terms — everything else on this client reads and writes whichever term is
  // current, so switching moves the whole session, not one request.
  listTerms: () => fetch(`${BASE}/terms`).then(json<TermList>),

  createTerm: (year: string, semester: Semester) =>
    fetch(`${BASE}/terms`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ year, semester }),
    }).then(json<Term>),

  setCurrentTerm: (term: string) =>
    fetch(`${BASE}/terms/current`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ term }),
    }).then(json<Term>),

  renameTerm: (term: string, year: string, semester: Semester) =>
    fetch(`${BASE}/terms/${term}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ year, semester }),
    }).then(json<Term>),

  // Freezes the undergraduate and joint week — day, hour and room — and stamps
  // the term released. Graduate courses stay fluid for phase 2.
  publishTerm: (term: string) =>
    fetch(`${BASE}/terms/${term}/publish?confirm=true`, { method: "POST" })
      .then(json<Term & { frozen: number }>),

  unpublishTerm: (term: string) =>
    fetch(`${BASE}/terms/${term}/publish?confirm=true`, { method: "DELETE" })
      .then(json<Term>),

  // Phase 2 — graduate courses placed around the published week.
  solveGrad: (timeLimit = 10) =>
    fetch(`${BASE}/solve/grad`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ time_limit_s: timeLimit }),
    }).then(json<SolveResult & { appended: string[] }>),

  rolloverPreview: () =>
    fetch(`${BASE}/terms/current/rollover`)
      .then(json<{ source: string; courses: RolloverCourse[] }>),

  rolloverApply: (numbers: string[]) =>
    fetch(`${BASE}/terms/current/rollover`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ numbers }),
    }).then(json<{ added: string[] }>),

  listCourses: () => fetch(`${BASE}/catalog/courses`).then(json<Course[]>),

  upsertCourse: (c: Course) =>
    fetch(`${BASE}/catalog/courses`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(c),
    }).then(json<Course>),

  deleteCourse: (n: string) =>
    fetch(`${BASE}/catalog/courses/${n}`, { method: "DELETE" }).then(json),

  seedCatalog: (force = false) =>
    fetch(`${BASE}/catalog/seed?force=${force}`, { method: "POST" }).then(
      json<{ seeded: number }>,
    ),

  exportCatalogUrl: () => `${BASE}/catalog/export.csv`,
  catalogTemplateUrl: () => `${BASE}/catalog/template.csv`,

  importCatalog: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch(`${BASE}/catalog/import`, { method: "POST", body: fd }).then(
      json<{ imported: number }>,
    );
  },

  solve: (timeLimit = 10) =>
    fetch(`${BASE}/solve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ time_limit_s: timeLimit }),
    }).then(json<SolveResult>),

  fixedEvents: () => fetch(`${BASE}/fixed-events`).then(json<FixedEvent[]>),

  evaluate: (placements: Record<string, Placement>) =>
    fetch(`${BASE}/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ placements }),
    }).then(json<EvalResult>),

  getAvailability: () => fetch(`${BASE}/availability`).then(json<Availability>),

  setAvailability: (availability: Availability) =>
    fetch(`${BASE}/availability`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(availability),
    }).then(json<{ people: string[] }>),

  getCalendar: () => fetch(`${BASE}/calendar`).then(json<Partial<SemesterCalendar>>),

  setCalendar: (cal: SemesterCalendar) =>
    fetch(`${BASE}/calendar`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cal),
    }).then(json<{ ok: boolean }>),

  analyzeCalendar: () => fetch(`${BASE}/calendar/analyze`).then(json<CalendarAnalysis>),

  uploadSkeleton: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch(`${BASE}/skeleton/upload`, { method: "POST", body: fd }).then(
      json<UploadResult>,
    );
  },

  getSkeletonRows: () => fetch(`${BASE}/skeleton/rows`).then(json<OfferedRow[]>),

  putSkeletonRows: (rows: OfferedRow[]) =>
    fetch(`${BASE}/skeleton/rows`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows }),
    }).then(json<{ count: number; offered: OfferedRow[] }>),

  clearSkeletonRows: () =>
    fetch(`${BASE}/skeleton/rows`, { method: "DELETE" }).then(
      json<{ count: number; offered: OfferedRow[] }>,
    ),

  skeletonCourseNumbers: () =>
    fetch(`${BASE}/skeleton/course-numbers`).then(
      json<{ imported: boolean; numbers: string[] }>,
    ),

  getPeople: () => fetch(`${BASE}/people`).then(json<Person[]>),

  setPeople: (items: Person[]) =>
    fetch(`${BASE}/people`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items }),
    }).then(json<Person[]>),

  importPeopleFromCatalog: () =>
    fetch(`${BASE}/people/import-from-catalog`, { method: "POST" }).then(json<Person[]>),

  getCoursesOfInterest: () =>
    fetch(`${BASE}/courses-of-interest`).then(json<CourseOfInterest[]>),

  setCoursesOfInterest: (items: CourseOfInterest[]) =>
    fetch(`${BASE}/courses-of-interest`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items }),
    }).then(json<CourseOfInterest[]>),

  coiExportUrl: () => `${BASE}/courses-of-interest/export.csv`,
  coiTemplateUrl: () => `${BASE}/courses-of-interest/template.csv`,

  importCoursesOfInterest: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch(`${BASE}/courses-of-interest/import`, { method: "POST", body: fd })
      .then(json<CourseOfInterest[]>);
  },

  exportCsvUrl: () => `${BASE}/export/csv`,
  exportPdfUrl: (layout: "cohort" | "flat" = "cohort") =>
    `${BASE}/export/pdf?layout=${layout}`,

  // ---- saved schedules (archive) ---- //
  getConfig: () => fetch(`${BASE}/config`).then(json<Config>),

  setSavesDir: (saves_dir: string) =>
    fetch(`${BASE}/config`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ saves_dir }),
    }).then(json<Config>),

  listSchedules: () => fetch(`${BASE}/schedules`).then(json<SavedMeta[]>),

  saveSchedule: (name: string, note?: string) =>
    fetch(`${BASE}/schedules`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, note }),
    }).then(json<SavedMeta>),

  // `confirm` is required only to load a save from another term — it carries a
  // whole catalog, so the wrong one replaces a semester's work.
  loadSchedule: (id: string, confirm = false) =>
    fetch(`${BASE}/schedules/${encodeURIComponent(id)}/load${confirm ? "?confirm=true" : ""}`,
          { method: "POST" }).then(json<SolveResult>),

  compareSchedules: (a: string, b: string) =>
    fetch(`${BASE}/schedules/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`)
      .then(json<ScheduleDiff>),

  renameSchedule: (id: string, name: string) =>
    fetch(`${BASE}/schedules/${encodeURIComponent(id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }).then(json<SavedMeta>),

  deleteSchedule: (id: string) =>
    fetch(`${BASE}/schedules/${encodeURIComponent(id)}`, { method: "DELETE" }).then(json),
};
