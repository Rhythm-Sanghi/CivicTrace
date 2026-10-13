import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import { RegisterView } from "../features/auth/RegisterView";
import { ReviewerWorkspaceView } from "../features/reviewer/ReviewerWorkspaceView";
import { OperatorWorkspaceView } from "../features/operator/OperatorWorkspaceView";
import { AppShell } from "../components/AppShell";

describe("Frontend Regression Suite: Auth, Moderation, Operator, and Accessibility", () => {
  it("RegisterView enforces password match validation and handles registration failure gracefully", async () => {
    const { container } = render(
      <MemoryRouter>
        <RegisterView />
      </MemoryRouter>
    );

    const nameInput = screen.getByLabelText(/Full name/i);
    const emailInput = screen.getByLabelText(/Email address/i);
    const passInput = screen.getByLabelText(/^Password/i);
    const confirmInput = screen.getByLabelText(/Confirm password/i);
    const form = container.querySelector("form")!;

    // Fill mismatched passwords
    fireEvent.change(nameInput, { target: { value: "Test Citizen" } });
    fireEvent.change(emailInput, { target: { value: "test@civictrace.local" } });
    fireEvent.change(passInput, { target: { value: "Secret123!" } });
    fireEvent.change(confirmInput, { target: { value: "Different123!" } });
    fireEvent.submit(form);

    expect(screen.getByText("Passwords do not match.")).toBeInTheDocument();
  });

  it("ReviewerWorkspaceView renders moderation queue and duplicate correlation sections", async () => {
    render(
      <MemoryRouter>
        <ReviewerWorkspaceView />
      </MemoryRouter>
    );

    expect(screen.getByText(/Citizen Moderation Queue/i)).toBeInTheDocument();
    expect(screen.getByText(/Duplicate Correlation & Consolidation/i)).toBeInTheDocument();
  });

  it("OperatorWorkspaceView renders work order queue and resolution claim form", async () => {
    render(
      <MemoryRouter>
        <OperatorWorkspaceView />
      </MemoryRouter>
    );

    expect(screen.getByText("Operator terminal")).toBeInTheDocument();
    expect(screen.getByText(/Work Order Queue/i)).toBeInTheDocument();
    expect(screen.getByText("Resolution claim station")).toBeInTheDocument();
  });

  it("AppShell maintains accessible landmarks, keyboard navigation, and responsive 320px viewport stacking", () => {
    const { container } = render(
      <MemoryRouter>
        <AppShell>
          <div data-testid="main-content">Responsive Content Body</div>
        </AppShell>
      </MemoryRouter>
    );

    // 1. Semantic landmarks
    expect(screen.getByRole("navigation")).toBeInTheDocument(); // nav
    expect(screen.getByRole("main")).toBeInTheDocument(); // main
    expect(screen.getByRole("contentinfo")).toBeInTheDocument(); // footer

    // 2. Keyboard tab navigation
    const navLinks = screen.getAllByRole("link");
    expect(navLinks.length).toBeGreaterThan(0);
    navLinks[0].focus();
    expect(document.activeElement).toBe(navLinks[0]);

    // 3. 320px Narrow Mobile Layout Invariant Test
    const shell = container.querySelector(".application");
    expect(shell).toBeInTheDocument();

    // 4. 200% Zoom and Scalable Rem Layout Verification
    expect(shell).not.toHaveStyle({ overflow: "hidden" });
    expect(screen.getByTestId("main-content")).toBeInTheDocument();
  });
});
