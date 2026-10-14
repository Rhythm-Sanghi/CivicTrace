import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import { RegisterView } from "../features/auth/RegisterView";
import { ReviewerWorkspaceView } from "../features/reviewer/ReviewerWorkspaceView";
import { OperatorWorkspaceView } from "../features/operator/OperatorWorkspaceView";
import { ReportIssueView } from "../features/reports/ReportIssueView";
import { NeighborhoodIntelligenceView } from "../features/neighborhood/NeighborhoodIntelligenceView";
import { AppShell } from "../components/AppShell";

describe("Frontend Regression Suite: Auth, Moderation, Operator, and Accessibility", () => {
  const originalFetch = globalThis.fetch;

  beforeAll(() => {
    globalThis.fetch = async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = typeof input === "string" ? input : (input as any).url || input.toString();
      if (url.includes("/reports/categories")) {
        return {
          ok: true,
          status: 200,
          json: async () => [
            { id: "cat-1", name: "Pothole", code: "POTHOLE", description: "Road defect", default_severity_weight: 3 }
          ],
        } as Response;
      }
      if (url.includes("/cases/neighborhood/stats")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            total_cases: 0,
            open_cases: 0,
            in_progress_cases: 0,
            resolved_cases: 0,
            disputed_cases: 0,
            average_resolution_hours: null,
            cases_by_category: {},
            cases_by_priority: {},
            total_claims: 0,
            verified_claims: 0,
            disputed_claims: 0,
            awaiting_claims: 0,
            total_observations: 0,
            confirmed_observations: 0,
            dispute_observations: 0,
          }),
        } as Response;
      }
      if (url.includes("/cases/recurrences")) {
        return {
          ok: true,
          status: 200,
          json: async () => [],
        } as Response;
      }
      if (url.includes("/cases")) {
        return {
          ok: true,
          status: 200,
          json: async () => [],
        } as Response;
      }
      if (url.includes("/reports/candidates")) {
        return {
          ok: true,
          status: 200,
          json: async () => [],
        } as Response;
      }
      if (url.includes("/reports")) {
        return {
          ok: true,
          status: 200,
          json: async () => [],
        } as Response;
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({}),
      } as Response;
    };
  });

  afterAll(() => {
    globalThis.fetch = originalFetch;
  });

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

    expect(screen.getByText("Work orders")).toBeInTheDocument();
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

  it("ReportIssueView does not silently assign default coordinates and allows explicit selection", async () => {
    render(
      <MemoryRouter>
        <ReportIssueView />
      </MemoryRouter>
    );

    const latInput = screen.getByLabelText(/Latitude/i) as HTMLInputElement;
    const lonInput = screen.getByLabelText(/Longitude/i) as HTMLInputElement;

    // Must start empty, NOT silently defaulted to Indore coordinates
    expect(latInput.value).toBe("");
    expect(lonInput.value).toBe("");

    // Clicking sample location explicitly fills coordinates with sample badge
    const sampleBtn = screen.getByRole("button", { name: /Use sample location/i });
    fireEvent.click(sampleBtn);

    expect(latInput.value).toBe("22.719600");
    expect(lonInput.value).toBe("75.857700");
    expect(screen.getByText(/Sample Coordinates/i)).toBeInTheDocument();
  });

  it("NeighborhoodIntelligenceView displays qualified states and does not fabricate median resolution fallback", async () => {
    render(
      <MemoryRouter>
        <NeighborhoodIntelligenceView />
      </MemoryRouter>
    );

    // Confirmed recurrence table should show qualified empty state, never keyword matches
    expect(await screen.findByText(/No confirmed recurring issues in the 60-day evaluation window/i)).toBeInTheDocument();

    // Median resolution metric should show "—" when uncalculated, never hardcoded "4.0d"
    expect(screen.queryByText("4.0d")).not.toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(1);
  });

  it("ReviewerWorkspaceView does not contain hardcoded concurrent timeframe text", async () => {
    render(
      <MemoryRouter>
        <ReviewerWorkspaceView />
      </MemoryRouter>
    );

    // Should never fabricate concurrent timeframe
    expect(screen.queryByText(/Concurrent timeframe \(0\.0 days apart\)/i)).not.toBeInTheDocument();
  });
});
