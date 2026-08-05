import { describe, expect, it } from "vitest";
import {
  GRAD_AUDIENCE, NO_FILTER, courseGroup, filterPlacements, filterWalls, type GridFilter,
} from "./gridFilter";
import type { FixedEvent, Placement, SessionMeta } from "./types";

function meta(over: Partial<SessionMeta> = {}): SessionMeta {
  return {
    course_number: "00540319",
    type: "lecture",
    group: null,
    length_boxes: 1,
    role: "core",
    cohorts: ["ChemE Y2"],
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

const at = (room_id = "hall1"): Placement => ({ day: 0, start_box: 0, room_id });

const filter = (over: Partial<GridFilter> = {}): GridFilter => ({ ...NO_FILTER, ...over });

// A three-session week: our UG course, a joint one, and a graduate one.
const SESSIONS: Record<string, SessionMeta> = {
  ug: meta({ course_number: "00540319", lecturers: ["dana"] }),
  joint: meta({ course_number: "00560111", cohorts: ["ChemE Y4"] }),
  grad: meta({ course_number: "00580222", cohorts: ["ChemE Y4"], lecturers: ["ron"] }),
  other: meta({ course_number: "01040032", cohorts: ["ChemE Y1"] }),
};
const PLACEMENTS: Record<string, Placement> = {
  ug: at("hall1"), joint: at("room3"), grad: at("room3"), other: at("hall6"),
};

const shown = (f: GridFilter) => Object.keys(filterPlacements(PLACEMENTS, SESSIONS, f)).sort();

describe("courseGroup", () => {
  it("maps each departmental prefix", () => {
    expect(courseGroup("00540319")).toBe("0054");
    expect(courseGroup("00560111")).toBe("0056");
    expect(courseGroup("00580222")).toBe("0058");
  });

  it("treats any other prefix as another faculty", () => {
    expect(courseGroup("01040032")).toBe("other");
    expect(courseGroup("")).toBe("other");
  });
});

describe("filterPlacements", () => {
  it("shows the whole week when nothing is ticked", () => {
    expect(shown(NO_FILTER)).toEqual(["grad", "joint", "other", "ug"]);
  });

  it("ORs the choices inside the course-number filter", () => {
    expect(shown(filter({ groups: ["0054", "0058"] }))).toEqual(["grad", "ug"]);
  });

  it("picks out another faculty's courses", () => {
    expect(shown(filter({ groups: ["other"] }))).toEqual(["other"]);
  });

  it("filters by undergraduate cohort", () => {
    expect(shown(filter({ audience: ["ChemE Y4"] }))).toEqual(["grad", "joint"]);
  });

  it("shows only graduate courses for the graduate audience", () => {
    expect(shown(filter({ audience: [GRAD_AUDIENCE] }))).toEqual(["grad"]);
  });

  it("ORs a cohort with the graduate audience", () => {
    expect(shown(filter({ audience: ["ChemE Y1", GRAD_AUDIENCE] }))).toEqual(["grad", "other"]);
  });

  it("ANDs across categories", () => {
    expect(shown(filter({ groups: ["0056"], rooms: ["room3"] }))).toEqual(["joint"]);
    expect(shown(filter({ groups: ["0056"], rooms: ["hall1"] }))).toEqual([]);
  });

  it("filters by lecturer", () => {
    expect(shown(filter({ lecturers: ["ron"] }))).toEqual(["grad"]);
  });

  it("drops sessions with no metadata once a filter is on", () => {
    const p = { ...PLACEMENTS, ghost: at() };
    expect(Object.keys(filterPlacements(p, SESSIONS, filter({ groups: ["0054"] })))).toEqual(["ug"]);
  });
});

describe("filterWalls", () => {
  const blackout: FixedEvent = {
    id: "bk-1", label: "Blackout", day: 2, start_box: 4, length_boxes: 2,
    kind: "blackout", cohorts: [],
  };
  const external: FixedEvent = {
    id: "ext-01040032", label: "Physics 1", day: 1, start_box: 3, length_boxes: 2,
    kind: "external", cohorts: ["ChemE Y1"],
  };
  const walls = [blackout, external];
  const ids = (f: GridFilter) => filterWalls(walls, f).map((w) => w.id);

  it("leaves the overlay alone when nothing is ticked", () => {
    expect(ids(NO_FILTER)).toEqual(["bk-1", "ext-01040032"]);
  });

  it("always keeps blackouts", () => {
    expect(ids(filter({ audience: [GRAD_AUDIENCE] }))).toEqual(["bk-1"]);
  });

  it("keeps an external wall for the cohort that takes it", () => {
    expect(ids(filter({ audience: ["ChemE Y1"] }))).toEqual(["bk-1", "ext-01040032"]);
    expect(ids(filter({ audience: ["ChemE Y4"] }))).toEqual(["bk-1"]);
  });

  it("follows the course-number filter via the wall's course number", () => {
    expect(ids(filter({ groups: ["other"] }))).toEqual(["bk-1", "ext-01040032"]);
    expect(ids(filter({ groups: ["0054"] }))).toEqual(["bk-1"]);
  });

  it("hides external walls under a room or lecturer filter", () => {
    expect(ids(filter({ rooms: ["hall1"] }))).toEqual(["bk-1"]);
    expect(ids(filter({ lecturers: ["dana"] }))).toEqual(["bk-1"]);
  });
});
