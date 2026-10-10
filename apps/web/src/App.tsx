import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Header } from "./components/Header";
import { HomeView } from "./features/home/HomeView";
import { CasesExplorerView } from "./features/cases/CasesExplorerView";
import { CaseDetailsView } from "./features/cases/CaseDetailsView";
import { ReportIssueView } from "./features/reports/ReportIssueView";
import { ReviewerWorkspaceView } from "./features/reviewer/ReviewerWorkspaceView";
import { OperatorWorkspaceView } from "./features/operator/OperatorWorkspaceView";
import { NeighborhoodIntelligenceView } from "./features/neighborhood/NeighborhoodIntelligenceView";
import { LoginView } from "./features/auth/LoginView";
import "./styles/tokens.css";

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
        <Header />
        <main style={{ flex: 1 }}>
          <Routes>
            <Route path="/" element={<HomeView />} />
            <Route path="/explorer" element={<CasesExplorerView />} />
            <Route path="/cases/:id" element={<CaseDetailsView />} />
            <Route path="/report" element={<ReportIssueView />} />
            <Route path="/reviewer" element={<ReviewerWorkspaceView />} />
            <Route path="/operator" element={<OperatorWorkspaceView />} />
            <Route path="/neighborhood" element={<NeighborhoodIntelligenceView />} />
            <Route path="/login" element={<LoginView />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        {/* Archival Utility Footer */}
        <footer style={{
          borderTop: "1px solid var(--color-border)",
          backgroundColor: "var(--color-surface)",
          padding: "var(--space-6) 0",
          fontSize: "var(--font-size-xs)",
          color: "var(--color-text-secondary)",
        }}>
          <div className="container" style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "10px" }}>
            <div>
              <strong>CivicTrace</strong> &bull; Public Record of Problems Worth Fixing. Open-Source Civic Accountability.
            </div>
            <div style={{ fontFamily: "var(--font-family-mono)" }}>
              SHA-256 LEDGER STANDARD &bull; INDORE WARD 34 DEMO AREA
            </div>
          </div>
        </footer>
      </div>
    </BrowserRouter>
  );
};

export default App;
