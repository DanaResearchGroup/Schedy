import type {
  Availability,
  CalendarAnalysis,
  Course,
  CourseOfInterest,
  FixedEvent,
  OfferedRow,
  Placement,
  SavedMeta,
  ScheduleDiff,
  SemesterCalendar,
  SessionMeta,
  SolveResult,
  Violation,
} from "./types";

export interface EvalResult {
  feasible: boolean;
  soft_penalty: number;
  sessions: Record<string, SessionMeta>;
  violations: Violation[];
}

export interface UploadResult {
  count: number;
  offered: OfferedRow[];
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

  getCoursesOfInterest: () =>
    fetch(`${BASE}/courses-of-interest`).then(json<CourseOfInterest[]>),

  setCoursesOfInterest: (items: CourseOfInterest[]) =>
    fetch(`${BASE}/courses-of-interest`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items }),
    }).then(json<CourseOfInterest[]>),

  exportCsvUrl: () => `${BASE}/export/csv`,
  exportPdfUrl: (layout: "cohort" | "flat" = "cohort") =>
    `${BASE}/export/pdf?layout=${layout}`,

  // ---- saved schedules (archive) ---- //
  getConfig: () => fetch(`${BASE}/config`).then(json<{ saves_dir: string }>),

  setSavesDir: (saves_dir: string) =>
    fetch(`${BASE}/config`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ saves_dir }),
    }).then(json<{ saves_dir: string }>),

  listSchedules: () => fetch(`${BASE}/schedules`).then(json<SavedMeta[]>),

  saveSchedule: (name: string, note?: string) =>
    fetch(`${BASE}/schedules`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, note }),
    }).then(json<SavedMeta>),

  loadSchedule: (id: string) =>
    fetch(`${BASE}/schedules/${encodeURIComponent(id)}/load`, { method: "POST" })
      .then(json<SolveResult>),

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
