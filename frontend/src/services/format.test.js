import { describe, expect, it } from "vitest";
import {
  dateLabel,
  dependencyText,
  fileSize,
  initials,
  isOverdue,
  slug,
} from "./format";

describe("real data formatting", () => {
  it("does not invent an unspecified date", () => {
    expect(dateLabel(null)).toBe("Not specified");
    expect(dateLabel("Friday")).toBe("Friday");
    expect(dateLabel("2026-10-01")).toContain("Oct");
  });
  it("respects action state for overdue tasks", () => {
    expect(
      isOverdue({ due_date: "2026-09-30", status: "Pending" }, "2026-10-01"),
    ).toBe(true);
    expect(
      isOverdue({ due_date: "2026-09-30", status: "Completed" }, "2026-10-01"),
    ).toBe(false);
    expect(
      isOverdue({ due_date: null, status: "Pending" }, "2026-10-01"),
    ).toBeFalsy();
  });
  it("handles source dependencies and human additions", () => {
    expect(dependencyText({ text: "Approval", evidence: [] })).toBe("Approval");
    expect(dependencyText("Approval")).toBe("Approval");
    expect(initials("Alex Morgan")).toBe("AM");
    expect(fileSize(10485760)).toBe("10.0 MB");
    expect(slug("In Progress")).toBe("in-progress");
  });
});
