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

describe("canDrop — a published session has no legal target", () => {
  it("refuses every drop for a published session", () => {
    // Its slot was handed to students; the evaluator scores a move as HARD
    // (published_moved), so the live hint must not offer anywhere to put it.
    const sessions: Record<string, SessionMeta> = {
      pub: meta({ published: true, fixed: true }),
    };
    expect(canDrop("pub", 3, 5, "hall6", {}, sessions, [])).toBe(false);
  });

  it("still allows a merely skeleton-anchored session to move", () => {
    // An anchor constrains the solver, not the planner — unchanged behaviour.
    const sessions: Record<string, SessionMeta> = { anc: meta({ fixed: true }) };
    expect(canDrop("anc", 3, 5, "hall6", {}, sessions, [])).toBe(true);
  });
});

describe("canDrop — the hard graduate rule (mirrors the evaluator)", () => {
  const grad = (over = {}) => meta({ level: "grad", role: "elective", ...over });

  it("refuses to drop a graduate course onto another graduate course", () => {
    const sessions: Record<string, SessionMeta> = {
      a: grad({ course_number: "00580001" }),
      b: grad({ course_number: "00580002" }),
    };
    expect(canDrop("a", 0, 0, "hall6", { b: at(0, 0, "hall1") }, sessions, []))
      .toBe(false);
  });

  it("refuses to drop a joint course onto a graduate course", () => {
    const sessions: Record<string, SessionMeta> = {
      j: meta({ level: "joint", course_number: "00560001" }),
      g: grad({ course_number: "00580001" }),
    };
    expect(canDrop("j", 0, 0, "hall6", { g: at(0, 0, "hall1") }, sessions, []))
      .toBe(false);
  });

  it("lets two joint courses overlap (D1)", () => {
    // Electives, so the existing cohort rule does not decide this for us — the
    // point is that the graduate rule alone must not reject it.
    const sessions: Record<string, SessionMeta> = {
      a: meta({ level: "joint", role: "elective", course_number: "00560001" }),
      b: meta({ level: "joint", role: "elective", course_number: "00560002" }),
    };
    expect(canDrop("a", 0, 0, "hall6", { b: at(0, 0, "hall1") }, sessions, []))
      .toBe(true);
  });

  it("lets alternatives of one cross-day lab overlap each other", () => {
    const sessions: Record<string, SessionMeta> = {
      a: grad({ course_number: "00580001", type: "lab", lab_group: "00580001" }),
      b: grad({ course_number: "00580001", type: "lab", lab_group: "00580001" }),
    };
    expect(canDrop("a", 0, 0, "hall6", { b: at(0, 0, "hall1") }, sessions, []))
      .toBe(true);
  });
});
