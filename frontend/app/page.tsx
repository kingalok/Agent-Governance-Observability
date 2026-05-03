import Link from "next/link";

import { AppShell } from "../components/app-shell";
import { MetricCard, SectionCard, StatusBadge, ToolPills } from "../components/dashboard-primitives";
import {
  getAgents,
  getDashboardSummary,
  getLogs,
  getPendingApprovals,
  getRuns,
} from "../lib/dashboard";

export default async function OverviewPage() {
  const [summary, agents, runs, approvals, logs] = await Promise.all([
    getDashboardSummary(),
    getAgents(),
    getRuns(),
    getPendingApprovals(),
    getLogs(),
  ]);

  return (
    <AppShell
      title="Overview"
      subtitle="Executive view of governed agent activity, approval pressure, and simulated usage economics."
    >
      <section className="metrics-grid">
        <MetricCard label="Total Runs" value={summary.total_runs} />
        <MetricCard label="Pending Approvals" value={summary.pending_approvals} />
        <MetricCard label="Successful Runs" value={summary.successful_runs} />
        <MetricCard label="Blocked Runs" value={summary.blocked_runs} />
        <MetricCard label="Simulated Tokens" value={`${summary.simulated_input_tokens + summary.simulated_output_tokens}`} />
        <MetricCard label="Simulated Cost" value={`$${summary.simulated_cost_usd.toFixed(2)}`} />
      </section>

      <section className="dashboard-grid">
        <SectionCard title="Run Health" action={<Link href="/runs" className="text-link">Open Run Explorer</Link>}>
          <div className="table-card">
            <div className="table-header table-grid compact-grid">
              <span>Run</span>
              <span>Agent</span>
              <span>Status</span>
              <span>Message</span>
            </div>
            {runs.slice(0, 5).map((run) => (
              <div key={run.run_id} className="table-row table-grid compact-grid">
                <strong>#{run.run_id}</strong>
                <span>{run.agent_name}</span>
                <StatusBadge value={run.status} />
                <span className="muted small">{run.message}</span>
              </div>
            ))}
          </div>
        </SectionCard>

        <SectionCard title="Approval Pressure" action={<Link href="/approvals" className="text-link">Open Queue</Link>}>
          <div className="stack">
            {approvals.slice(0, 4).map((approval) => (
              <article key={approval.id} className="approval-card">
                <div className="row">
                  <strong>Run #{approval.run_id}</strong>
                  <StatusBadge value={approval.status} />
                </div>
                <p className="muted small">{approval.action_name}</p>
                <p className="small">{approval.reason}</p>
              </article>
            ))}
          </div>
        </SectionCard>
      </section>

      <section className="dashboard-grid">
        <SectionCard title="Agent Registry Snapshot" action={<Link href="/agents" className="text-link">Open Registry</Link>}>
          <div className="stack">
            {agents.map((agent) => (
              <article key={agent.id} className="agent-card">
                <div className="topline">
                  <StatusBadge value={agent.risk_tier ?? "low"} />
                  <StatusBadge value={agent.status} />
                </div>
                <h3>{agent.name}</h3>
                <p className="muted small">
                  {agent.owner_name} · {agent.team_name}
                </p>
                <ToolPills tools={agent.allowed_tools ?? []} />
              </article>
            ))}
          </div>
        </SectionCard>

        <SectionCard title="Recent Events">
          <div className="stack">
            {logs.slice(0, 5).map((log) => (
              <article key={log.id} className="log-card">
                <div className="row">
                  <strong>{log.event_type}</strong>
                  <StatusBadge value={log.level} />
                </div>
                <p className="muted small">{log.workflow_name ?? "workflow"}</p>
                <p className="small">{log.message}</p>
              </article>
            ))}
          </div>
        </SectionCard>
      </section>
    </AppShell>
  );
}
