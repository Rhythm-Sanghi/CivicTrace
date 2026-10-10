import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppShell } from "./components/AppShell";
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
      <AppShell>
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
      </AppShell>
    </BrowserRouter>
  );
};

export default App;
