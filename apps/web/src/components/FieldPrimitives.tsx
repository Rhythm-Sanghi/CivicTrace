import React from "react";
import { Link } from "react-router-dom";

// CivicTrace Page Header Primitive
export interface PageHeadingProps {
  index?: string;
  eyebrow?: string;
  title: string;
  description?: string;
  children?: React.ReactNode;
}

export const PageHeading: React.FC<PageHeadingProps> = ({
  index,
  title,
  description,
  children,
}) => {
  return (
    <header className="page-header">
      <div className="page-heading">
        {index && (
          <span className="page-index" aria-hidden="true">
            {index} /
          </span>
        )}
        <div>
          <h1 id="page-title">{title}</h1>
          {description && <p>{description}</p>}
        </div>
      </div>
      {children && <div className="header-toolbar">{children}</div>}
    </header>
  );
};

// CivicTrace Metric Strip Primitive
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

// CivicTrace Status Stamp Primitive
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

// CivicTrace Section Header Primitive
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
    <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
      {actionText && (
        actionHref ? (
          <Link to={actionHref} className="section-detail">
            {actionText}
          </Link>
        ) : (
          <span className="section-detail">{actionText}</span>
        )
      )}
      {children}
    </div>
  </div>
);
