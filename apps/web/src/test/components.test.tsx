import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { LoginView } from "../features/auth/LoginView";

describe("Frontend Core Components & Design System", () => {
  it("renders AppShell brand and primary navigation items", () => {
    render(
      <MemoryRouter>
        <AppShell>
          <div>Child workspace</div>
        </AppShell>
      </MemoryRouter>
    );

    expect(screen.getByText("CivicTrace")).toBeInTheDocument();
    expect(screen.getByText("Field Ledger Standard")).toBeInTheDocument();
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Case Explorer")).toBeInTheDocument();
    expect(screen.getByText("Intelligence")).toBeInTheDocument();
    expect(screen.getByText("Report Issue")).toBeInTheDocument();
    expect(screen.getByText("Child workspace")).toBeInTheDocument();
  });

  it("renders Login view with demo role credentials", () => {
    render(
      <MemoryRouter>
        <LoginView />
      </MemoryRouter>
    );

    expect(screen.getByText("CivicTrace Portal Sign-In")).toBeInTheDocument();
    expect(screen.getByText(/Community Reviewer:/)).toBeInTheDocument();
    expect(screen.getByText(/Public Works Operator:/)).toBeInTheDocument();
    expect(screen.getByText(/Citizen Observer:/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sign In/i })).toBeInTheDocument();
  });
});
