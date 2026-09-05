import type { Decision, RiskLevel } from "@/lib/types";

const RISK_BORDER: Record<RiskLevel, string> = {
  LOW: "border-l-riskLow",
  MEDIUM: "border-l-riskMedium",
  HIGH: "border-l-riskHigh",
  CRITICAL: "border-l-riskCritical",
};

const RISK_TEXT: Record<RiskLevel, string> = {
  LOW: "text-riskLow",
  MEDIUM: "text-riskMedium",
  HIGH: "text-riskHigh",
  CRITICAL: "text-riskCritical",
};

function formatAmount(amount: number): string {
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(amount);
}

export default function TransactionFeed({ decisions }: { decisions: Decision[] }) {
  if (decisions.length === 0) {
    return (
      <div className="border border-border bg-panel p-8 text-center">
        <p className="text-sm text-textSecondary">No decisions yet. Run the streaming pipeline to populate this feed.</p>
      </div>
    );
  }

  return (
    <div className="border border-border bg-panel">
      <div className="border-b border-border px-4 py-3">
        <p className="text-sm text-textSecondary">Recent decisions</p>
      </div>
      <div>
        {decisions.map((d) => (
          <div
            key={d.transaction_id}
            className={`flex flex-col gap-1 border-b border-border border-l-4 ${RISK_BORDER[d.risk_level]} px-4 py-3 last:border-b-0 sm:flex-row sm:items-center sm:gap-4`}
          >
            <span className="w-24 shrink-0 truncate font-mono text-xs text-textMuted">
              {d.transaction_id}
            </span>
            <span className="w-28 shrink-0 text-right font-mono text-sm text-textPrimary">
              Rs. {formatAmount(d.amount)}
            </span>
            <span className={`w-20 shrink-0 font-mono text-xs ${RISK_TEXT[d.risk_level]}`}>
              {d.risk_level}
            </span>
            <span className="w-20 shrink-0 font-mono text-xs text-textSecondary">
              {d.final_decision}
            </span>
            <span className="w-16 shrink-0 font-mono text-xs text-textSecondary">
              {(d.fraud_probability * 100).toFixed(1)}%
            </span>
            <span className="min-w-0 flex-1 truncate text-xs text-textMuted">
              {d.explanation}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
