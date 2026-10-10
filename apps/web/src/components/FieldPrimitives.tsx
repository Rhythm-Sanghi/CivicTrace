import React from "react";
import { Link } from "react-router-dom";

// 1. Page Heading Primitive
export interface PageHeadingProps {
  eyebrow?: string;
  title: string;
  description?: string;
  children?: React.ReactNode;
}

export const PageHeading: React.FC<PageHeadingProps> = ({
  eyebrow,
  title,
  description,
  children,
}) => (
  <div className="page-header">
    <div>
      {eyebrow && <div className="page-eyebrow">{eyebrow}</div>}
      <h1 className="page-title">{title}</h1>
      {description && <p className="page-description">{description}</p>}
    </div>
    {children && <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>{children}</div>}
  </div>
);

// 2. Metric Strip Primitive
export interface MetricItem {
  label: string;
  value: string | number;
  description?: string;
  accentColor?: string;
}

export interface MetricStripProps {
  metrics: MetricItem[];
}

export const MetricStrip: React.FC<MetricStripProps> = ({ metrics }) => (
  <div className="metric-strip">
    {metrics.map((m, idx) => (
      <div key={idx} className="metric-cell">
        <div className="metric-cell-label" style={{ color: m.accentColor || undefined }}>
          {m.label}
        </div>
        <div className="metric-cell-value" style={{ color: m.accentColor || "var(--color-text-primary)" }}>
          {m.value}
        </div>
        {m.description && <div className="metric-cell-desc">{m.description}</div>}
      </div>
    ))}
  </div>
);

// 3. Status Stamp Primitive
export interface StatusStampProps {
  state: string;
  size?: "sm" | "md";
}

export const StatusStamp: React.FC<StatusStampProps> = ({ state, size = "md" }) => {
  const norm = state.toLowerCase();
  return (
    <span
      className={`archival-stamp stamp-${norm}`}
      style={{ fontSize: size === "sm" ? "10px" : "11px" }}
    >
      {state.replace(/_/g, " ")}
    </span>
  );
};

// 4. Dark-Ink Section Header Primitive
export interface SectionHeaderProps {
  title: string;
  actionText?: string;
  actionHref?: string;
  children?: React.ReactNode;
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({
  title,
  actionText,
  actionHref,
  children,
}) => (
  <div style={{
    backgroundColor: "var(--color-ink-rail)",
    color: "#FFF",
    padding: "10px 16px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    fontSize: "11px",
    fontFamily: "var(--font-family-mono)",
    fontWeight: 600,
    letterSpacing: "0.06em",
    textTransform: "uppercase",
    borderTopLeftRadius: "var(--radius-sm)",
    borderTopRightRadius: "var(--radius-sm)",
    borderBottom: "1px solid var(--color-ink-rail-border)",
  }}>
    <span>{title}</span>
    {actionText && actionHref && (
      <Link to={actionHref} style={{ color: "#9BC0D6", textDecoration: "none", fontSize: "11px" }}>
        {actionText} &rarr;
      </Link>
    )}
    {children}
  </div>
);
