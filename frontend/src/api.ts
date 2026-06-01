import type { Course, Placement, SolveResult, Violation } from "./types";

export interface EvalResult {
  feasible: boolean;
  soft_penalty: number;
  violations: Violation[];
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

  solve: (timeLimit = 10) =>
    fetch(`${BASE}/solve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ time_limit_s: timeLimit }),
    }).then(json<SolveResult>),

  evaluate: (placements: Record<string, Placement>) =>
    fetch(`${BASE}/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ placements }),
    }).then(json<EvalResult>),

  exportCsvUrl: () => `${BASE}/export/csv`,
  exportPdfUrl: () => `${BASE}/export/pdf`,
};
