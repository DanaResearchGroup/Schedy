import { describe, expect, it } from "vitest";
import { parseSemester } from "./types";

// Everything in the app is scoped to a term, so a misread semester does not
// fail — it quietly files a year's work under the wrong half of the year. The
// parser therefore refuses what it does not recognise rather than guessing.
describe("parseSemester", () => {
  it("reads the full word in either language", () => {
    expect(parseSemester("winter")).toBe("winter");
    expect(parseSemester("spring")).toBe("spring");
    expect(parseSemester("חורף")).toBe("winter");
    expect(parseSemester("אביב")).toBe("spring");
  });

  it("accepts an unambiguous abbreviation", () => {
    expect(parseSemester("w")).toBe("winter");
    expect(parseSemester("spr")).toBe("spring");
    expect(parseSemester("א")).toBe("spring");
  });

  it("ignores case and surrounding space", () => {
    expect(parseSemester("  Spring ")).toBe("spring");
    expect(parseSemester("WINTER")).toBe("winter");
  });

  it("refuses a typo instead of defaulting to winter", () => {
    // The bug this exists to prevent: "sprng" is not spring, and answering
    // "winter" to it puts a term's catalog somewhere nobody looks.
    expect(parseSemester("sprng")).toBeNull();
    expect(parseSemester("summer")).toBeNull();
    expect(parseSemester("x")).toBeNull();
  });

  it("refuses an empty answer", () => {
    expect(parseSemester("")).toBeNull();
    expect(parseSemester("   ")).toBeNull();
  });
});
