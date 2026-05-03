import Link from "next/link";
import { ReactNode } from "react";

import { getStatusTone } from "../lib/dashboard";

export function MetricCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number;
  hint?: string;
}) {
  return (
    <article className="panel metric-card">
      <p className="muted small">{label}</p>
      <div className="metric-value">{value}</div>
      {hint ? <p className="muted small">{hint}</p> : null}
    </article>
  );
}

export function SectionCard({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <div className="section-head">
        <h3 className="section-title">{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}

export function StatusBadge({ value }: { value: string }) {
  return <span className={`badge ${getStatusTone(value)}`}>{value.replaceAll("_", " ")}</span>;
}

export function ToolPills({ tools }: { tools: string[] }) {
  return (
    <div className="tool-list">
      {tools.map((tool) => (
        <span key={tool} className="tool-pill">
          {tool}
        </span>
      ))}
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p className="muted small">{description}</p>
    </div>
  );
}

export function RunLink({ runId, label }: { runId: number; label: string }) {
  return (
    <Link href={`/runs/${runId}`} className="run-link">
      {label}
    </Link>
  );
}
