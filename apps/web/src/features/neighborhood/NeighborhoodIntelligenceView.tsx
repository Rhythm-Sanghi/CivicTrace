import React, { useEffect, useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { api, type NeighborhoodStats, type Case, type RecurrenceRelationship } from "../../lib/api";
import { PageHeading, MetricStrip, SectionHeader, StatusStamp } from "../../components/FieldPrimitives";

export const NeighborhoodIntelligenceView: React.FC = () => {
  const [stats, setStats] = useState<NeighborhoodStats | null>(null);
  const [cases, setCases] = useState<Case[]>([]);
  const [recurrences, setRecurrences] = useState<RecurrenceRelationship[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.getNeighborhoodStats().catch(() => null),
      api.getCases().catch(() => []),
      api.getRecurrences().catch(() => []),
    ])
      .then(([s, cList, rList]) => {
        setStats(s);
        setCases(cList);
        setRecurrences(rList);
        setLoading(false);
      })
      .catch((err) => {
        setErrorMsg(err.message || "Failed to load intelligence metrics");
        setLoading(false);
      });
  }, []);

  const [referenceTime] = useState(() => Date.now());

  // Compute live distributions from real cases
  const {
    stateDistribution,
    ageDistribution,
    categoryDistribution,
    openCasesCount,
    resolvedCasesCount,
  } = useMemo(() => {
    const statesCount: Record<string, number> = {};
    const ageBuckets = { "< 24h": 0, "1–3 days": 0, "4–7 days": 0, "> 7 days": 0 };
    const catMap: Record<string, number> = {};

    let openCount = 0;
    let resolvedCount = 0;

    cases.forEach((c) => {
      // 1. Lifecycle State count
      statesCount[c.state] = (statesCount[c.state] || 0) + 1;
      if (c.state === "RESOLVED") {
        resolvedCount++;
      } else if (c.state !== "REJECTED") {
        openCount++;
      }

      // 2. Age distribution
      const createdTime = new Date(c.created_at).getTime();
      const ageHours = Math.max(0, (referenceTime - createdTime) / (1000 * 3600));
      if (ageHours < 24) ageBuckets["< 24h"]++;
      else if (ageHours <= 72) ageBuckets["1–3 days"]++;
      else if (ageHours <= 168) ageBuckets["4–7 days"]++;
      else ageBuckets["> 7 days"]++;

      // 3. Category distribution
      const catName = c.category?.name || "Uncategorized";
      catMap[catName] = (catMap[catName] || 0) + 1;
    });

    return {
      stateDistribution: Object.entries(statesCount).map(([st, cnt]) => ({
        state: st,
        count: cnt,
        percentage: cases.length ? ((cnt / cases.length) * 100).toFixed(0) : "0",
      })),
      ageDistribution: Object.entries(ageBuckets).map(([bucket, cnt]) => ({
        bucket,
        count: cnt,
        percentage: cases.length ? ((cnt / cases.length) * 100).toFixed(0) : "0",
      })),
      categoryDistribution: Object.entries(catMap).map(([name, cnt]) => ({
        name,
        count: cnt,
        percentage: cases.length ? ((cnt / cases.length) * 100).toFixed(0) : "0",
      })),
      openCasesCount: openCount,
      resolvedCasesCount: resolvedCount,
    };
  }, [cases, referenceTime]);

  if (loading) {
    return (
      <div className="workspace">
        <p className="muted">Loading neighborhood intelligence...</p>
      </div>
    );
  }

  if (errorMsg) {
    return (
      <div className="workspace">
        <div role="alert" style={{ color: "var(--danger)", padding: "var(--space-4)", background: "var(--surface)", border: "1px solid var(--danger)" }}>
          {errorMsg}
        </div>
      </div>
    );
  }

  // Calculate genuine verification and dispute rates from real claim records
  const totalClaims = stats?.total_claims ?? 0;
  const verifiedClaims = stats?.verified_claims ?? 0;
  const disputedClaims = stats?.disputed_claims ?? 0;
  const awaitingClaims = stats?.awaiting_claims ?? 0;

  const verifRate = totalClaims > 0
    ? `${((verifiedClaims / totalClaims) * 100).toFixed(0)}%`
    : "—";

  const disputeRate = totalClaims > 0
    ? `${((disputedClaims / totalClaims) * 100).toFixed(0)}%`
    : "—";

  const medianDuration = stats && stats.median_resolution_days > 0
    ? `${stats.median_resolution_days}d`
    : "—";

  return (
    <>
      <PageHeading
        title="Intelligence"
        description="Public repair and resolution patterns computed from verifiable community reports. All metrics reflect recorded ledger activity."
      />

      <div className="workspace">
        <MetricStrip
          metrics={[
            {
              label: "Independent verification rate",
              value: verifRate,
              accentColor: "var(--success)",
            },
            {
              label: "Dispute rate (of claims)",
              value: disputeRate,
              accentColor: "var(--danger)",
            },
            {
              label: "Median duration",
              value: medianDuration,
            },
            {
              label: "Recorded observations",
              value: stats ? stats.total_reports : cases.length,
            },
          ]}
        />

        <div className="responsive-grid-2" style={{ marginBottom: "var(--space-5)" }}>
          {/* Defect Distribution Table */}
          <div>
            <SectionHeader
              title="Defect distribution by category"
              actionText={`${cases.length} total cases`}
            />

            <div className="table-shell">
              <table>
                <thead>
                  <tr>
                    <th>Infrastructure class</th>
                    <th className="numeric" style={{ width: "80px" }}>Cases</th>
                    <th className="numeric" style={{ width: "80px" }}>Share</th>
                  </tr>
                </thead>
                <tbody>
                  {categoryDistribution.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="muted" style={{ textAlign: "center" }}>No category records available</td>
                    </tr>
                  ) : (
                    categoryDistribution.map((item) => (
                      <tr key={item.name}>
                        <td>{item.name}</td>
                        <td className="numeric font-mono">{item.count}</td>
                        <td className="numeric font-mono">{item.percentage}%</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Cases by Lifecycle State (Never call resolved cases 'outstanding') */}
          <div>
            <SectionHeader
              title="Cases by workflow state"
              actionText={`${openCasesCount} active · ${resolvedCasesCount} resolved`}
            />

            <div className="table-shell">
              <table>
                <thead>
                  <tr>
                    <th>Workflow state</th>
                    <th className="numeric" style={{ width: "80px" }}>Cases</th>
                    <th className="numeric" style={{ width: "80px" }}>Share</th>
                  </tr>
                </thead>
                <tbody>
                  {stateDistribution.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="muted" style={{ textAlign: "center" }}>No case records available</td>
                    </tr>
                  ) : (
                    stateDistribution.map((item) => (
                      <tr key={item.state}>
                        <td>
                          <StatusStamp state={item.state} size="sm" />
                        </td>
                        <td className="numeric font-mono">{item.count}</td>
                        <td className="numeric font-mono">{item.percentage}%</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Lower Grid: Age Distribution & Genuine Recurrence / Claims */}
        <div className="responsive-grid-2">
          {/* Case Age Distribution */}
          <div>
            <SectionHeader
              title="Case age distribution"
              actionText={`${cases.length} records`}
            />

            <div className="table-shell">
              <table>
                <thead>
                  <tr>
                    <th>Age since report</th>
                    <th className="numeric" style={{ width: "80px" }}>Cases</th>
                    <th className="numeric" style={{ width: "80px" }}>Share</th>
                  </tr>
                </thead>
                <tbody>
                  {ageDistribution.map((item) => (
                    <tr key={item.bucket}>
                      <td>{item.bucket}</td>
                      <td className="numeric font-mono">{item.count}</td>
                      <td className="numeric font-mono">{item.percentage}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "6px" }}>
              Sample size: {cases.length} cases registered in this service area.
            </div>
          </div>

          {/* Resolution Verification Audits & Confirmed Recurrence */}
          <div>
            <SectionHeader
              title="Claim verification & recurrence"
              actionText={recurrences.length > 0 ? `${recurrences.length} confirmed recurring` : undefined}
            />

            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", padding: "var(--space-4)" }}>
              {/* Claims Breakdown Row */}
              <div style={{ marginBottom: "var(--space-3)", paddingBottom: "var(--space-3)", borderBottom: "1px solid var(--border)" }}>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "var(--space-2)", fontWeight: 600 }}>
                  RESOLUTION CLAIM VERIFICATION BREAKDOWN
                </div>
                {totalClaims > 0 ? (
                  <div style={{ display: "flex", gap: "var(--space-4)", fontSize: "12px", flexWrap: "wrap" }}>
                    <div>
                      <span style={{ color: "var(--success)", fontWeight: 600 }}>■ Verified: </span>
                      <span className="font-mono">{verifiedClaims}</span>
                    </div>
                    <div>
                      <span style={{ color: "var(--danger)", fontWeight: 600 }}>■ Disputed: </span>
                      <span className="font-mono">{disputedClaims}</span>
                    </div>
                    <div>
                      <span style={{ color: "var(--warning)", fontWeight: 600 }}>■ Awaiting audit: </span>
                      <span className="font-mono">{awaitingClaims}</span>
                    </div>
                  </div>
                ) : (
                  <p className="muted" style={{ margin: 0, fontSize: "12px" }}>
                    No formal resolution claims submitted yet. Rates will calculate as operators file claims.
                  </p>
                )}
              </div>

              {/* Recurrence Window Section (60 days per backend engine policy) */}
              <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "var(--space-2)", fontWeight: 600 }}>
                CONFIRMED RECURRING ISSUES (&lt; 60 DAYS RE-EMERGENCE)
              </div>

              {recurrences.length > 0 ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                  {recurrences.map((rel) => {
                    const currentCase = cases.find((c) => c.id === rel.current_case_id);
                    const caseRef = currentCase?.public_id || rel.current_case_id;
                    const caseTitle = currentCase?.title || "Recurring infrastructure defect";
                    const caseAddr = currentCase?.address_reference || "Same physical location";

                    return (
                      <div
                        key={rel.id}
                        style={{
                          padding: "var(--space-2) var(--space-3)",
                          border: "1px solid var(--border)",
                          borderLeft: "3px solid var(--warning)",
                          background: "var(--surface-muted)",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "4px" }}>
                          <code style={{ fontSize: "11px", fontWeight: 600 }}>{caseRef}</code>
                          <span style={{ fontSize: "10px", color: "var(--warning)", fontWeight: 600 }}>
                            {rel.is_reviewer_confirmed ? "REVIEWER CONFIRMED" : "MATHEMATICALLY CONFIRMED"}
                          </span>
                        </div>
                        <div style={{ fontWeight: 600, fontSize: "13px", marginTop: "4px" }}>
                          <Link to={`/cases/${caseRef}`} style={{ color: "var(--text-primary)" }}>
                            {caseTitle}
                          </Link>
                        </div>
                        <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "2px" }}>
                          {caseAddr} · Resolved {rel.days_since_prior_resolution}d prior ({rel.distance_meters.toFixed(0)}m distance)
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="empty" style={{ margin: 0, padding: "var(--space-3) 0" }}>
                  No confirmed recurring issues in the 60-day evaluation window.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
};
