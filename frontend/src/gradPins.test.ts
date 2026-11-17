import { describe, expect, it } from "vitest";
import { showReleaseGradPins } from "./gradPins";

describe("showReleaseGradPins", () => {
  it("shows for an unpublished term holding pins, with no session metadata at all", () => {
    expect(showReleaseGradPins({ "00580001-lec": {} }, false)).toBe(true);
  });
  it("hides when nothing is pinned", () => {
    expect(showReleaseGradPins({}, false)).toBe(false);
  });
  it("hides while published, where the published freeze already holds", () => {
    expect(showReleaseGradPins({ "00580001-lec": {} }, true)).toBe(false);
  });
});
