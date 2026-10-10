import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import { Header } from "../components/Header";
import { LoginView } from "../features/auth/LoginView";

describe("Frontend Core Components & Design System", () => {
  it("renders Header brand and primary navigation items", () => {
    render(
      <MemoryRouter>
        <Header />
      </MemoryRouter>
    );

    expect(screen.getByText("CivicTrace")).toBeInTheDocument();
    expect(screen.getByText("Public Evidence Ledger")).toBeInTheDocument();
    expect(screen.getByText("Public Cases")).toBeInTheDocument();
    expect(screen.getByText("Intelligence & Metrics")).toBeInTheDocument();
    expect(screen.getByText("Report Issue")).toBeInTheDocument();
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
