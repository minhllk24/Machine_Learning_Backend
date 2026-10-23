import React from "react";
import { ShieldAlert, Database, Lock } from "lucide-react";

export const GovernanceFooter: React.FC = () => {
  return (
    <footer
      style={{
        marginTop: "auto",
        borderTop: "1px solid var(--border-subtle)",
        background: "rgba(10, 14, 23, 0.7)",
        padding: "1.25rem 2.5rem",
        fontSize: "0.75rem",
        color: "var(--text-dim)",
      }}
    >
      <div
        style={{
          maxWidth: "1440px",
          margin: "0 auto",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "1rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "1.25rem" }}>
          <span style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <Database size={13} style={{ color: "var(--status-info)" }} />
            Dataset: <strong>UCI Online Retail II (2009–2011)</strong>
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <ShieldAlert size={13} style={{ color: "var(--status-warning)" }} />
            Context: <code>current_market_applicability_assessed = FALSE</code>
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <Lock size={13} style={{ color: "var(--primary-500)" }} />
            Model Registry: <strong>Frozen Artifacts (No synthetic inference)</strong>
          </span>
        </div>
        <div>
          <span>Phase 13–15 Production Release &bull; Academic Research & Operations System</span>
        </div>
      </div>
    </footer>
  );
};
