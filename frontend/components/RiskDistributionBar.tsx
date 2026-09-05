import type { DecisionStats, RiskLevel } from "@/lib/types";

const RISK_ORDER: RiskLevel[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

const RISK_COLOR: Record<RiskLevel, string> = {
  LOW: "bg-riskLow",
  MEDIUM: "bg-riskMedium",
  HIGH: "bg-riskHigh",
  CRITICAL: "bg-riskCritical",
};

const RISK_TEXT_COLOR: Record<RiskLevel, string> = {
  LOW: "text-riskLow",
  MEDIUM: "text-riskMedium",
  HIGH: "text-riskHigh",
  CRITICAL: "text-riskCritical",
};

export default function RiskDistributionBar({ stats }: { stats: DecisionStats }) {
  const total = stats.total || 1; // avoid divide-by-zero when empty

  return (
    <div className="border border-border bg-panel p-4">
      <p className="text-sm text-textSecondary">Risk level distribution</p>

      <div className="mt-3 flex h-3 w-full overflow-hidden">
        {RISK_ORDER.map((level) => {
          const count = stats.by_risk_level[level] ?? 0;
          const widthPct = (count / total) * 100;
          if (widthPct === 0) return null;
          return (
            <div
              key={level}
              className={RISK_COLOR[level]}
              style={{ width: `${widthPct}%` }}
              title={`${level}: ${count}`}
            />
          );
        })}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {RISK_ORDER.map((level) => (
          <div key={level} className="flex items-baseline gap-2">
            <span className={`h-2 w-2 shrink-0 ${RISK_COLOR[level]}`} />
            <span className={`text-xs ${RISK_TEXT_COLOR[level]}`}>{level}</span>
            <span className="font-mono text-xs text-textSecondary">
              {stats.by_risk_level[level] ?? 0}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
