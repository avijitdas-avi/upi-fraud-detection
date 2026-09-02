"""
Apply the rule engine to the full behavioral-features dataset and
report how well the rules alone separate fraud from legitimate
transactions.

This is a standalone evaluation of the rule-based layer in isolation —
it does not involve the ML model (Phase 5) or the combined decision
layer (Phase 6). The point is to see, before any ML is introduced,
how much fraud these deterministic checks already catch and at what
false-positive cost, since that's the baseline the ML model will need
to meaningfully improve on.

Usage (run as a module from the project root, since this script
imports from the `src` package):
    python -m src.rules.run_rules \
        --input data/processed/behavioral_features.csv \
        --output data/processed/rule_engine_results.csv
"""

from __future__ import annotations

import argparse

import pandas as pd

from src.rules.engine import RuleEngine


def apply_rule_engine(df: pd.DataFrame) -> pd.DataFrame:
    engine = RuleEngine()
    triggered_ids = []
    triggered_counts = []

    for _, row in df.iterrows():
        output = engine.evaluate(row)
        triggered_ids.append(",".join(output.triggered_rule_ids))
        triggered_counts.append(output.triggered_count)

    df = df.copy()
    df["triggered_rules"] = triggered_ids
    df["triggered_rule_count"] = triggered_counts
    df["any_rule_triggered"] = df["triggered_rule_count"] > 0
    return df


def print_evaluation(df: pd.DataFrame) -> None:
    from src.rules.definitions import build_default_rules

    total_fraud = int(df["label_is_fraud"].sum())
    total_legit = int((~df["label_is_fraud"]).sum())

    flagged = df["any_rule_triggered"]
    true_positives = int((flagged & df["label_is_fraud"]).sum())
    false_positives = int((flagged & ~df["label_is_fraud"]).sum())
    false_negatives = total_fraud - true_positives

    precision = true_positives / flagged.sum() if flagged.sum() else 0.0
    recall = true_positives / total_fraud if total_fraud else 0.0

    print("=== Rule Engine Evaluation (rules only, no ML) ===\n")
    print(f"Total transactions:        {len(df)}")
    print(f"Total fraud:                {total_fraud}")
    print(f"Total legitimate:           {total_legit}\n")
    print(f"Flagged by >=1 rule:        {int(flagged.sum())} ({flagged.mean():.1%} of all transactions)")
    print(f"  True positives (caught):  {true_positives}")
    print(f"  False positives:          {false_positives}")
    print(f"  False negatives (missed): {false_negatives}\n")
    print(f"Precision (of flagged, % actually fraud): {precision:.1%}")
    print(f"Recall (of fraud, % flagged):              {recall:.1%}\n")

    print("--- Per-rule trigger counts ---")
    for rule in build_default_rules():
        col_mask = df["triggered_rules"].str.contains(rule.rule_id, regex=False)
        rule_total = int(col_mask.sum())
        rule_tp = int((col_mask & df["label_is_fraud"]).sum())
        rule_precision = rule_tp / rule_total if rule_total else 0.0
        print(f"  {rule.rule_id:28s} triggered {rule_total:5d}x  "
              f"({rule_tp:4d} were fraud, precision={rule_precision:.1%})")

    print("\n--- Fraud caught by rule count ---")
    caught = df.loc[df["label_is_fraud"] & df["any_rule_triggered"]]
    missed = df.loc[df["label_is_fraud"] & ~df["any_rule_triggered"]]
    print(f"  Fraud caught by at least one rule: {len(caught)} / {total_fraud}")
    print(f"  Fraud missed by all rules:         {len(missed)} / {total_fraud}")
    if len(missed):
        print("  Fraud types missed most often:")
        print(missed["fraud_type"].value_counts().to_string())


def main():
    parser = argparse.ArgumentParser(description="Apply the rule engine to the behavioral features dataset.")
    parser.add_argument("--input", type=str, default="data/processed/behavioral_features.csv")
    parser.add_argument("--output", type=str, default="data/processed/rule_engine_results.csv")
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    df["label_is_fraud"] = df["label_is_fraud"].astype(bool)

    results = apply_rule_engine(df)
    results.to_csv(args.output, index=False)

    print(f"Wrote {len(results)} rows with rule engine results to {args.output}\n")
    print_evaluation(results)


if __name__ == "__main__":
    main()
