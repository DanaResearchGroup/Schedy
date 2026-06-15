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

  // Forbidden regions: blackouts close every cohort; external walls only the
  // cohorts they belong to.
  for (const w of walls) {
    if (w.day !== day) continue;
    const applies = w.kind === "blackout" || s.cohorts.some((c) => w.cohorts.includes(c));
    if (applies && overlaps(w.start_box, w.length_boxes)) return false;
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
    const labExempt = labExemptSelf || o.lab_group != null;
    if (!labExempt && s.cohorts.some((c) => o.cohorts.includes(c))) return false; // cohort clash
  }
  return true;
}
