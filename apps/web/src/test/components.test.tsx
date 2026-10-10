import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { LoginView } from "../features/auth/LoginView";

describe("Frontend Core Components & Benchlight Design System", () => {
  it("renders AppShell brand, numbered navigation, and offline status footer", () => {
    render(
      <MemoryRouter>
        <AppShell>
          <div>Child workspace</div>
        </AppShell>
      </MemoryRouter>
    );

    expect(screen.getByText("CivicTrace")).toBeInTheDocument();
    expect(screen.getByText("01")).toBeInTheDocument();
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("02")).toBeInTheDocument();
    expect(screen.getByText("Cases")).toBeInTheDocument();
    expect(screen.getByText("03")).toBeInTheDocument();
    expect(screen.getByText("Intelligence")).toBeInTheDocument();
    expect(screen.getByText("04")).toBeInTheDocument();
    expect(screen.getByText("Report issue")).toBeInTheDocument();
    expect(screen.getByText("Local SQLite Workspace")).toBeInTheDocument();
    expect(screen.getByText("Child workspace")).toBeInTheDocument();
  });

  it("renders Login view with demo role credentials", () => {
    render(
      <MemoryRouter>
        <LoginView />
      </MemoryRouter>
    );

    expect(screen.getByText("CivicTrace Portal Sign-In")).toBeInTheDocument();
    expect(screen.getByText("Citizen (Aarav)")).toBeInTheDocument();
    expect(screen.getByText("Reviewer (Rajesh)")).toBeInTheDocument();
    expect(screen.getByText("Operator (Kavita)")).toBeInTheDocument();
    expect(screen.getByText("Administrator")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sign In to Portal/i })).toBeInTheDocument();
  });
});
