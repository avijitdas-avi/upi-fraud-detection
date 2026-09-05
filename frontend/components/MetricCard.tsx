interface MetricCardProps {
  label: string;
  value: string;
  sublabel?: string;
  emphasis?: boolean;
}

export default function MetricCard({ label, value, sublabel, emphasis }: MetricCardProps) {
  return (
    <div className="border border-border bg-panel p-4">
      <p className="text-sm text-textSecondary">{label}</p>
      <p className={emphasis ? "mt-1 font-mono text-4xl font-medium text-textPrimary" : "mt-1 font-mono text-2xl font-medium text-textPrimary"}>
        {value}
      </p>
      {sublabel && <p className="mt-1 text-xs text-textMuted">{sublabel}</p>}
    </div>
  );
}
