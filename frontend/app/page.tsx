"use client";

import { useEffect, useState, useCallback } from "react";
import MetricCard from "@/components/MetricCard";
import RiskDistributionBar from "@/components/RiskDistributionBar";
import TransactionFeed from "@/components/TransactionFeed";
import ScoreTransactionForm from "@/components/ScoreTransactionForm";
import { getStats, getRecentDecisions } from "@/lib/api";
import type { Decision, DecisionStats } from "@/lib/types";

const POLL_INTERVAL_MS = 5000;

const EMPTY_STATS: DecisionStats = {
  total: 0,
  by_decision: { ALLOW: 0, REVIEW: 0, BLOCK: 0 },
  by_risk_level: { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 },
};

export default function DashboardPage() {
  const [stats, setStats] = useState<DecisionStats>(EMPTY_STATS);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [statsResult, decisionsResult] = await Promise.all([
        getStats(),
        getRecentDecisions(50),
      ]);
      setStats(statsResult);
      setDecisions(decisionsResult);
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't reach the backend.");
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  const blockRate = stats.total > 0 ? (stats.by_decision.BLOCK / stats.total) * 100 : 0;

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <div className="flex items-baseline justify-between border-b border-border pb-4">
        <div>
          <h1 className="text-lg font-medium text-textPrimary">UPI fraud detection</h1>
          <p className="text-sm text-textSecondary">Live transaction risk console</p>
        </div>
        <p className="font-mono text-xs text-textMuted">
          {lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : "Connecting..."}
        </p>
      </div>

      {error && (
        <div className="mt-4 border border-riskCritical bg-panel px-4 py-3">
          <p className="text-sm text-riskCritical">{error}</p>
          <p className="mt-1 text-xs text-textMuted">
            Check that the backend is running and NEXT_PUBLIC_API_URL points at it.
          </p>
        </div>
      )}

      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetricCard label="Decisions scored" value={stats.total.toLocaleString()} emphasis />
        <MetricCard label="Allowed" value={stats.by_decision.ALLOW.toLocaleString()} />
        <MetricCard label="Flagged for review" value={stats.by_decision.REVIEW.toLocaleString()} />
        <MetricCard label="Blocked" value={stats.by_decision.BLOCK.toLocaleString()} sublabel={`${blockRate.toFixed(1)}% of total`} />
      </div>

      <div className="mt-4">
        <RiskDistributionBar stats={stats} />
      </div>

      <div className="mt-4">
        <ScoreTransactionForm />
      </div>

      <div className="mt-4">
        <TransactionFeed decisions={decisions} />
      </div>
    </main>
  );
}
