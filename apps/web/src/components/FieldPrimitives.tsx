import React from "react";
import { Link } from "react-router-dom";

// 1. Benchlight Page Header Primitive
export interface PageHeadingProps {
  index?: string;
  eyebrow?: string; // fallback if index omitted
  title: string;
  description?: string;
  children?: React.ReactNode;
}

export const PageHeading: React.FC<PageHeadingProps> = ({
  index = "01",
  eyebrow,
  title,
  description,
  children,
}) => {
  const displayIndex = index || (eyebrow ? eyebrow.slice(0, 2) : "01");
  return (
    <header className="page-header">
      <div className="page-heading">
        <span className="page-index" aria-hidden="true">
          {displayIndex} /
        </span>
        <div>
          <h1 id="page-title">{title}</h1>
          {description && <p>{description}</p>}
        </div>
      </div>
      {children && <div className="header-toolbar">{children}</div>}
    </header>
  );
};

// 2. Benchlight Flat Measurement / Metric Strip Primitive
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
  <dl className="measurement" aria-label="Key civic metrics">
    {metrics.map((m, idx) => (
      <div key={idx}>
        <dt>{m.label}</dt>
        <dd style={{ color: m.accentColor || undefined }}>{m.value}</dd>
      </div>
    ))}
  </dl>
);

// 3. Benchlight Status Mark Primitive (Restrained colored square + label)
export interface StatusStampProps {
  state: string;
  size?: "sm" | "md";
}

export const StatusStamp: React.FC<StatusStampProps> = ({ state }) => {
  const norm = state.toLowerCase();
  let stateClass = "state-progress";
  if (norm.includes("verified") || norm.includes("resolved")) {
    stateClass = "state-verified";
  } else if (norm.includes("disputed") || norm.includes("rejected")) {
    stateClass = "state-disputed";
  } else if (norm.includes("awaiting") || norm.includes("submitted") || norm.includes("claim")) {
    stateClass = "state-awaiting";
  }

  return (
    <span className={`state-label ${stateClass}`}>
      <span className="state-mark" aria-hidden="true" />
      <span>{state.replace(/_/g, " ")}</span>
    </span>
  );
};

// 4. Benchlight Section Heading Primitive
export interface SectionHeaderProps {
  index?: string;
  title: string;
  actionText?: string;
  actionHref?: string;
  children?: React.ReactNode;
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({
  index,
  title,
  actionText,
  actionHref,
  children,
}) => (
  <div className="section-heading">
    <h2>
      {index && <span className="section-index">{index}</span>}
      {title}
    </h2>
    <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
      {actionText && actionHref && (
        <Link to={actionHref} className="section-detail">
          {actionText}
        </Link>
      )}
      {children}
    </div>
  </div>
);
