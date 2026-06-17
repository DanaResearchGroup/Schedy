import { describe, expect, it } from "vitest";
import { canDrop } from "./dropCheck";
import type { FixedEvent, Placement, SessionMeta } from "./types";

// Build a SessionMeta with sane defaults; override only what a test cares about.
function meta(over: Partial<SessionMeta> = {}): SessionMeta {
  return {
    course_number: "00540319",
    type: "lecture",
    group: null,
    length_boxes: 1,
    role: "core",
    cohorts: ["ChemE-2"],
    lecturers: [],
    tas: [],
    is_remote: false,
    fixed: false,
    enrollment: 30,
    needs_farm: false,
    lab_group: null,
    ...over,
  };
}

const at = (day: number, start_box: number, room_id = "hall1"): Placement => ({
  day,
  start_box,
  room_id,
});

describe("canDrop — elective cohort overlaps are soft (must mirror the evaluator)", () => {
  it("lets an elective drop onto a core course of the same cohort", () => {
    // The evaluator scores elective-vs-core as SOFT, so the live hint must NOT
    // paint it as a hard 'cannot drop'.
    const sessions: Record<string, SessionMeta> = {
      core: meta({ course_number: "00540320" }),
      elec: meta({ course_number: "00540319", role: "elective" }),
    };
    const placements = { core: at(0, 0, "hall1") };
    expect(
      canDrop("elec", 0, 0, "hall6", placements, sessions, []),
    ).toBe(true);
  });

  it("lets an elective overlap an external wall of the same cohort", () => {
    const sessions: Record<string, SessionMeta> = {
      elec: meta({ role: "elective" }),
    };
    const wall: FixedEvent = {
      id: "ext1",
      label: "Faculty seminar",
      day: 0,
      start_box: 0,
      length_boxes: 2,
      kind: "external",
      cohorts: ["ChemE-2"],
    };
    expect(canDrop("elec", 0, 0, "hall1", {}, sessions, [wall])).toBe(true);
  });

  it("still blocks two core courses sharing a cohort (unchanged)", () => {
    const sessions: Record<string, SessionMeta> = {
      a: meta({ course_number: "00540320" }),
      b: meta({ course_number: "00540319" }),
    };
    expect(
      canDrop("b", 0, 0, "hall6", { a: at(0, 0, "hall1") }, sessions, []),
    ).toBe(false);
  });

  it("still blocks an elective from a blackout (blackouts are hard for everyone)", () => {
    const sessions: Record<string, SessionMeta> = { elec: meta({ role: "elective" }) };
    const blackout: FixedEvent = {
      id: "bk",
      label: "Reserve duty",
      day: 0,
      start_box: 0,
      length_boxes: 2,
      kind: "blackout",
      cohorts: [],
    };
    expect(canDrop("elec", 0, 0, "hall1", {}, sessions, [blackout])).toBe(false);
  });
});

describe("canDrop — coincident TA sessions of one course are a hard clash", () => {
  it("blocks two overlapping exercise groups of the same course even with different TAs", () => {
    // Distinct cohorts and distinct TAs, so neither the cohort-clash nor the
    // person-clash rule fires — only the same-course TA-coincidence rule can.
    const sessions: Record<string, SessionMeta> = {
      ex1: meta({ type: "exercise", group: "SE011", tas: ["ta_a"], cohorts: ["ChemE-2"] }),
      ex2: meta({ type: "exercise", group: "SE012", tas: ["ta_b"], cohorts: ["ChemE-3"] }),
    };
    expect(
      canDrop("ex2", 0, 0, "hall6", { ex1: at(0, 0, "hall1") }, sessions, []),
    ).toBe(false);
  });

  it("allows overlapping exercise groups of DIFFERENT courses (no coincidence rule)", () => {
    const sessions: Record<string, SessionMeta> = {
      ex1: meta({ course_number: "00540319", type: "exercise", tas: ["ta_a"], cohorts: ["A"] }),
      ex2: meta({ course_number: "00540320", type: "exercise", tas: ["ta_b"], cohorts: ["B"] }),
    };
    expect(
      canDrop("ex2", 0, 0, "hall6", { ex1: at(0, 0, "hall1") }, sessions, []),
    ).toBe(true);
  });
});
