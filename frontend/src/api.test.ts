import { describe, expect, it } from "vitest";
import { detailText } from "./api";

describe("detailText", () => {
  it("passes a plain string through", () => {
    expect(detailText("nope")).toBe("nope");
  });
  it("shows the message then each violation", () => {
    const out = detailText({
      message: "not caused by the graduate pins",
      violations: [{ kind: "capacity_exceeded", message: "too big", session_ids: ["a-lec"] }],
      preview: {},
    });
    expect(out).toBe("not caused by the graduate pins\n- capacity_exceeded: too big (a-lec)");
  });
  it("returns null for anything else", () => {
    expect(detailText(undefined)).toBeNull();
    expect(detailText([{ loc: [] }])).toBeNull();
  });
});
