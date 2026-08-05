// Which sessions the weekly grid shows.
//
// Four independent categories, each multi-select. Picking nothing in a category
// means "no constraint", so the empty filter shows the whole week. Choices
// inside one category OR together (0054 *or* 0056); the categories AND
// (a 0054 course *and* in hall1).

import type { FixedEvent, Placement, SessionMeta } from "./types";

// The leading four digits of a course number carry the department's taxonomy:
// 0054 is our own undergraduate teaching, 0056 is joint undergraduate/graduate,
// 0058 is purely graduate, and anything else comes from another faculty. See
// docs/grad-scheduling-prd.md — a course will eventually be able to store its
// level explicitly, but the number is what the catalog gives us today.
export type CourseGroup = "0054" | "0056" | "0058" | "other";

const DEPT_PREFIXES = ["0054", "0056", "0058"] as const;
export const COURSE_GROUPS: CourseGroup[] = [...DEPT_PREFIXES, "other"];

export function courseGroup(courseNumber: string): CourseGroup {
  const prefix = courseNumber.trim().slice(0, 4);
  return DEPT_PREFIXES.find((p) => p === prefix) ?? "other";
}

export const isGraduate = (courseNumber: string) => courseGroup(courseNumber) === "0058";

// A graduate audience has no cohort — a graduate student is not "ChemE Y2" — so
// it rides in the cohort list under a reserved token. The `*` cannot collide
// with a cohort label, which is always "<program> Y<year>".
export const GRAD_AUDIENCE = "*grad";

export interface GridFilter {
  /** `CourseGroup` values. */
  groups: string[];
  /** Cohort labels, plus `GRAD_AUDIENCE` for the graduate courses. */
  audience: string[];
  /** Room ids. */
  rooms: string[];
  /** Lecturer ids. */
  lecturers: string[];
}

export const NO_FILTER: GridFilter = { groups: [], audience: [], rooms: [], lecturers: [] };

/** How many choices are ticked across every category; 0 means "show everything". */
export const filterCount = (f: GridFilter): number =>
  f.groups.length + f.audience.length + f.rooms.length + f.lecturers.length;

const matches = (chosen: string[], has: (value: string) => boolean) =>
  chosen.length === 0 || chosen.some(has);

/** Cohorts a session serves, plus the graduate token when the course is 0058. */
const audienceOf = (courseNumber: string, cohorts: string[]) =>
  isGraduate(courseNumber) ? [...cohorts, GRAD_AUDIENCE] : cohorts;

export function filterPlacements(
  placements: Record<string, Placement>,
  sessions: Record<string, SessionMeta>,
  f: GridFilter,
): Record<string, Placement> {
  if (filterCount(f) === 0) return placements;
  const out: Record<string, Placement> = {};
  for (const [sid, p] of Object.entries(placements)) {
    const m = sessions[sid];
    if (!m) continue; // no metadata, nothing to match a filter against
    const keep =
      matches(f.groups, (g) => g === courseGroup(m.course_number)) &&
      matches(f.audience, (a) => audienceOf(m.course_number, m.cohorts).includes(a)) &&
      matches(f.rooms, (r) => r === p.room_id) &&
      matches(f.lecturers, (l) => m.lecturers.includes(l));
    if (keep) out[sid] = p;
  }
  return out;
}

// An external course's wall is built as `ext-<course number>` (catalog.py).
const wallCourseNumber = (w: FixedEvent) => (w.id.startsWith("ext-") ? w.id.slice(4) : "");

/**
 * Keep the wall overlay consistent with the blocks underneath it.
 *
 * Blackouts are global and always stay. External-course walls belong to the
 * cohorts that take the course, so they follow the course and audience filters.
 * A room or lecturer filter asks about a resource rather than about someone's
 * week, and an external course occupies neither of ours — so those hide it.
 */
export function filterWalls(walls: FixedEvent[], f: GridFilter): FixedEvent[] {
  if (filterCount(f) === 0) return walls;
  return walls.filter((w) => {
    if (w.kind === "blackout") return true;
    if (f.rooms.length > 0 || f.lecturers.length > 0) return false;
    const number = wallCourseNumber(w);
    return (
      matches(f.groups, (g) => number !== "" && g === courseGroup(number)) &&
      matches(f.audience, (a) => audienceOf(number, w.cohorts).includes(a))
    );
  });
}
