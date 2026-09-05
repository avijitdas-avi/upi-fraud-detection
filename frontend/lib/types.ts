export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type FinalDecision = "ALLOW" | "REVIEW" | "BLOCK";

export interface Decision {
  transaction_id: string;
  sender_upi_id: string;
  receiver_upi_id: string;
  amount: number;
  transaction_type: string;
  fraud_probability: number;
  risk_level: RiskLevel;
  triggered_rules: string[];
  final_decision: FinalDecision;
  explanation: string;
  scored_at: string;
}

export interface DecisionStats {
  total: number;
  by_decision: Record<FinalDecision, number>;
  by_risk_level: Record<RiskLevel, number>;
}

export interface ScoreTransactionInput {
  transaction_id: string;
  sender_upi_id: string;
  receiver_upi_id: string;
  amount: number;
  transaction_type: string;
  device_id: string;
  location: string;
}
