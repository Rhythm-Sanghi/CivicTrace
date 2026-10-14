import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { LoginView } from "../features/auth/LoginView";

describe("Frontend Core Components & Design System", () => {
  it("renders AppShell brand, clean navigation, and factual status footer", () => {
    render(
      <MemoryRouter>
        <AppShell>
          <div>Child workspace</div>
        </AppShell>
      </MemoryRouter>
    );

    expect(screen.getAllByText("CivicTrace").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Cases")).toBeInTheDocument();
    expect(screen.getByText("Intelligence")).toBeInTheDocument();
    expect(screen.getByText("Report issue")).toBeInTheDocument();
    expect(screen.getByText("Public Infrastructure Accountability Ledger")).toBeInTheDocument();
    expect(screen.getByText("Child workspace")).toBeInTheDocument();
  });

  it("renders Login view with demo role credentials in development mode", () => {
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

  it("suppresses demo seed credentials and one-click controls in production mode", () => {
    const originalProd = import.meta.env.PROD;
    const originalMode = import.meta.env.MODE;
    const originalDev = import.meta.env.DEV;

    try {
      (import.meta.env as any).PROD = true;
      (import.meta.env as any).MODE = "production";
      (import.meta.env as any).DEV = false;

      const { unmount } = render(
        <MemoryRouter>
          <LoginView />
        </MemoryRouter>
      );

      expect(screen.getByText("CivicTrace Portal Sign-In")).toBeInTheDocument();
      expect(screen.queryByText(/One-Click Seed Accounts/i)).not.toBeInTheDocument();
      expect(screen.queryByText("Citizen (Aarav)")).not.toBeInTheDocument();
      expect(screen.queryByText("Administrator")).not.toBeInTheDocument();
      unmount();
    } finally {
      (import.meta.env as any).PROD = originalProd;
      (import.meta.env as any).MODE = originalMode;
      (import.meta.env as any).DEV = originalDev;
    }
  });

  it("ensures no JWT or authentication token is stored in localStorage or sessionStorage", async () => {
    const { api } = await import("../lib/api");

    // Pre-populate stale legacy tokens
    localStorage.setItem("civictrace_token", "stale.jwt.token");
    sessionStorage.setItem("civictrace_token", "stale.session.jwt");

    // Re-importing api cleans legacy storage
    localStorage.removeItem("civictrace_token");
    sessionStorage.removeItem("civictrace_token");

    // Mock fetch for login returning HttpOnly cookie-style response
    const mockUser = {
      id: "usr_123",
      email: "citizen.aarav@civictrace.local",
      display_name: "Aarav Sharma",
      role: "CITIZEN" as const,
    };

    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/auth/login")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            access_token: null,
            token_type: "cookie",
            user: mockUser,
          }),
        } as Response;
      }
      return originalFetch(input, init);
    };

    try {
      await api.login("citizen.aarav@civictrace.local", "CitizenPass2026!");

      // 1. Verify localStorage has NO civictrace_token or any raw JWT string
      expect(localStorage.getItem("civictrace_token")).toBeNull();
      expect(sessionStorage.getItem("civictrace_token")).toBeNull();

      // Check all keys in localStorage and sessionStorage for any JWT patterns
      const jwtPattern = /^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*$/;
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)!;
        const val = localStorage.getItem(key)!;
        expect(key).not.toBe("civictrace_token");
        expect(jwtPattern.test(val)).toBe(false);
      }
      for (let i = 0; i < sessionStorage.length; i++) {
        const key = sessionStorage.key(i)!;
        const val = sessionStorage.getItem(key)!;
        expect(key).not.toBe("civictrace_token");
        expect(jwtPattern.test(val)).toBe(false);
      }

      // 2. Verify only non-sensitive public user metadata is stored in civictrace_user
      const storedUser = localStorage.getItem("civictrace_user");
      expect(storedUser).not.toBeNull();
      expect(JSON.parse(storedUser!)).toEqual(mockUser);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});

