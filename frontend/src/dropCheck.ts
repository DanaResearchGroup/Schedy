import type { FixedEvent, Placement, SessionMeta } from "./types";
import { ROOMS } from "./types";

const BOXES = 10; // 08:30..18:30

// A best-effort, client-side preview of whether dropping a session at a given
// day/box/room would create a HARD conflict — mirroring the server evaluator's
// hard rules so the grid can highlight legal targets live during a drag. It is
// intentionally a preview: person-availability (which the frontend doesn't hold)
// isn't checked here, so the authoritative /evaluate on drop remains the source
// of truth. Returns true when the drop is allowed.
export function canDrop(
  sid: string,
  day: number,
  startBox: number,
  roomId: string | undefined,
  placements: Record<string, Placement>,
  sessions: Record<string, SessionMeta>,
  walls: FixedEvent[],
): boolean {
  const s = sessions[sid];
  if (!s) return true;
  const len = Math.max(1, s.length_boxes);
  const a0 = startBox;
  const a1 = startBox + len; // half-open [a0, a1)
  if (a0 < 0 || a1 > BOXES) return false; // would spill off the grid

  const overlaps = (b0: number, blen: number) => {
    const b1 = b0 + Math.max(1, blen);
    return a0 < b1 && b0 < a1;
  };

  // Forbidden regions: blackouts close every cohort (hard for everyone). An
  // external wall only blocks its own cohorts — and even then only as a SOFT
  // cost for electives (elective_vs_core), so the hint must not reject those.
  const isElective = s.role === "elective";
  for (const w of walls) {
    if (w.day !== day || !overlaps(w.start_box, w.length_boxes)) continue;
    if (w.kind === "blackout") return false;
    if (!isElective && s.cohorts.some((c) => w.cohorts.includes(c))) return false;
  }

  // Room capacity / computer-farm need for the target room.
  const rm = ROOMS.find((r) => r.id === roomId);
  if (rm) {
    if (s.needs_farm && !rm.farm) return false;
    if (s.enrollment > rm.capacity) return false;
  }

  // Pairwise clashes against every other placed session on this day.
  const labExemptSelf = s.lab_group != null; // cross-day labs may overlap cores
  for (const [oid, p] of Object.entries(placements)) {
    if (oid === sid || p.day !== day) continue;
    const o = sessions[oid];
    if (!o || !overlaps(p.start_box, o.length_boxes)) continue;

    if (roomId && p.room_id === roomId) return false; // room double-booked
    const sharePerson =
      s.lecturers.some((x) => o.lecturers.includes(x) || o.tas.includes(x)) ||
      s.tas.some((x) => o.lecturers.includes(x) || o.tas.includes(x));
    if (sharePerson) return false; // a lecturer/TA can't be in two places

    // Two exercise groups of the same course may never run at once. Mirrors the
    // evaluator's `ta_sessions_coincide` hard rule, which turns on course number
    // and type alone — it holds whether or not the groups share a TA or a cohort.
    if (s.type === "exercise" && o.type === "exercise" && s.course_number === o.course_number)
      return false;

    // Cohort clash is HARD only between two non-elective, non-lab sessions:
    // electives are a SOFT cost (elective_vs_*) and cross-day labs may overlap.
    const labExempt = labExemptSelf || o.lab_group != null;
    const electiveExempt = isElective || o.role === "elective";
    if (!labExempt && !electiveExempt && s.cohorts.some((c) => o.cohorts.includes(c)))
      return false; // cohort clash
  }
  return true;
}
