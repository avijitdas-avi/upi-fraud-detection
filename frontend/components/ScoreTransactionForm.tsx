"use client";

import { useState } from "react";
import type { Decision, RiskLevel } from "@/lib/types";
import { scoreTransaction } from "@/lib/api";

const RISK_TEXT: Record<RiskLevel, string> = {
  LOW: "text-riskLow",
  MEDIUM: "text-riskMedium",
  HIGH: "text-riskHigh",
  CRITICAL: "text-riskCritical",
};

const TRANSACTION_TYPES = ["P2P", "P2M", "COLLECT"];

function randomId(): string {
  return `demo_${Math.random().toString(36).slice(2, 10)}`;
}

export default function ScoreTransactionForm() {
  const [senderUpiId, setSenderUpiId] = useState("test_sender@upi");
  const [receiverUpiId, setReceiverUpiId] = useState("test_receiver@upi");
  const [amount, setAmount] = useState("500");
  const [transactionType, setTransactionType] = useState(TRANSACTION_TYPES[0]);
  const [deviceId, setDeviceId] = useState("dev_test_001");
  const [location, setLocation] = useState("Kolkata");

  const [result, setResult] = useState<Decision | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const parsedAmount = Number(amount);
    if (!senderUpiId.trim() || !receiverUpiId.trim() || !deviceId.trim() || !location.trim()) {
      setError("Fill in every field before scoring.");
      return;
    }
    if (!Number.isFinite(parsedAmount) || parsedAmount <= 0) {
      setError("Enter an amount greater than 0.");
      return;
    }

    setLoading(true);
    try {
      const decision = await scoreTransaction({
        transaction_id: randomId(),
        sender_upi_id: senderUpiId,
        receiver_upi_id: receiverUpiId,
        amount: parsedAmount,
        transaction_type: transactionType,
        device_id: deviceId,
        location,
      });
      setResult(decision);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scoring failed — is the backend reachable?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="border border-border bg-panel p-4">
      <p className="text-sm text-textSecondary">Score a transaction</p>

      <form onSubmit={handleSubmit} className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs text-textSecondary">
          Sender UPI ID
          <input
            className="border border-border bg-base px-2 py-1.5 font-mono text-sm text-textPrimary outline-none focus:border-accent"
            value={senderUpiId}
            onChange={(e) => setSenderUpiId(e.target.value)}
          />
        </label>

        <label className="flex flex-col gap-1 text-xs text-textSecondary">
          Receiver UPI ID
          <input
            className="border border-border bg-base px-2 py-1.5 font-mono text-sm text-textPrimary outline-none focus:border-accent"
            value={receiverUpiId}
            onChange={(e) => setReceiverUpiId(e.target.value)}
          />
        </label>

        <label className="flex flex-col gap-1 text-xs text-textSecondary">
          Amount (INR)
          <input
            className="border border-border bg-base px-2 py-1.5 font-mono text-sm text-textPrimary outline-none focus:border-accent"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            inputMode="decimal"
          />
        </label>

        <label className="flex flex-col gap-1 text-xs text-textSecondary">
          Transaction type
          <select
            className="border border-border bg-base px-2 py-1.5 font-mono text-sm text-textPrimary outline-none focus:border-accent"
            value={transactionType}
            onChange={(e) => setTransactionType(e.target.value)}
          >
            {TRANSACTION_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs text-textSecondary">
          Device ID
          <input
            className="border border-border bg-base px-2 py-1.5 font-mono text-sm text-textPrimary outline-none focus:border-accent"
            value={deviceId}
            onChange={(e) => setDeviceId(e.target.value)}
          />
        </label>

        <label className="flex flex-col gap-1 text-xs text-textSecondary">
          Location
          <input
            className="border border-border bg-base px-2 py-1.5 font-mono text-sm text-textPrimary outline-none focus:border-accent"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
          />
        </label>

        <div className="sm:col-span-2">
          <button
            type="submit"
            disabled={loading}
            className="border border-borderStrong bg-base px-4 py-2 text-sm text-textPrimary hover:border-accent disabled:opacity-50"
          >
            {loading ? "Scoring..." : "Score transaction"}
          </button>
        </div>
      </form>

      {error && <p className="mt-3 text-xs text-riskCritical">{error}</p>}

      {result && (
        <div className="mt-4 border-t border-border pt-4">
          <div className="flex flex-wrap items-baseline gap-4">
            <span className={`font-mono text-lg ${RISK_TEXT[result.risk_level]}`}>
              {result.risk_level}
            </span>
            <span className="font-mono text-sm text-textPrimary">{result.final_decision}</span>
            <span className="font-mono text-sm text-textSecondary">
              {(result.fraud_probability * 100).toFixed(1)}% probability
            </span>
          </div>
          <p className="mt-2 text-xs text-textMuted">{result.explanation}</p>
          {result.triggered_rules.length > 0 && (
            <p className="mt-2 font-mono text-xs text-textSecondary">
              Rules: {result.triggered_rules.join(", ")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
