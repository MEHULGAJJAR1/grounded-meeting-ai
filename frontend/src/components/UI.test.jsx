import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Button, Field, SupportBadge } from "./UI";
import { Evidence } from "./Evidence";

afterEach(cleanup);
describe("accessible data-driven controls", () => {
  it("cannot submit while busy even with disabled=false", () => {
    render(
      <Button busy disabled={false}>
        Save action
      </Button>,
    );
    expect(screen.getByRole("button")).toBeDisabled();
  });
  it("distinguishes source review from human-provided records", () => {
    render(
      <>
        <SupportBadge item={{ grounding_status: "review", confidence: 0.55 }} />
        <SupportBadge item={{ source_type: "manual" }} />
      </>,
    );
    expect(screen.getByText("Needs review")).toBeInTheDocument();
    expect(screen.getByText("User provided")).toBeInTheDocument();
  });
  it("labels selects independently of their option text and hint", () => {
    render(
      <Field label="Priority" hint="Application default if not specified">
        <select>
          <option>Medium</option>
          <option>High</option>
        </select>
      </Field>,
    );
    expect(
      screen.getByLabelText("Priority", { exact: true }),
    ).toHaveAccessibleDescription("Application default if not specified");
  });
  it("labels nested password inputs without labelling the visibility button", () => {
    render(
      <Field label="Password">
        <div>
          <input type="password" />
          <button type="button">Show password</button>
        </div>
      </Field>,
    );
    expect(screen.getByLabelText("Password", { exact: true })).toHaveAttribute(
      "type",
      "password",
    );
  });
  it("expands real quotes and locates the actual source", () => {
    const locate = vi.fn();
    const evidence = [
      { quote: "Rahul will write the runbook.", line_start: 2, line_end: 2 },
    ];
    render(<Evidence evidence={evidence} onLocate={locate} />);
    fireEvent.click(screen.getByRole("button", { name: /source quote/ }));
    expect(
      screen.getByText("Rahul will write the runbook."),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /View in transcript/ }));
    expect(locate).toHaveBeenCalledWith(evidence[0]);
  });
});
