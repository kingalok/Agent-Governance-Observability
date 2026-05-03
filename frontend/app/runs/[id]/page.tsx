import { notFound } from "next/navigation";

import { AppShell } from "../../../components/app-shell";
import { KillRunForm } from "../../../components/kill-run-form";
import { SectionCard, StatusBadge, ToolPills } from "../../../components/dashboard-primitives";
import { getRunDetail, getRunEvents } from "../../../lib/dashboard";

export default async function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const runId = Number(id);
  if (Number.isNaN(runId)) notFound();

  const [run, events] = await Promise.all([getRunDetail(runId), getRunEvents(runId)]);
  const state = run.graph_state ?? {};
  const execution = (run.final_output.execution_result ?? state.execution_result ?? {}) as Record<string, unknown>;
  const classification = String(run.classification_label ?? state.classification_label ?? "unclassified");
  const reasoning = String(run.reasoning_summary ?? state.reasoning_summary ?? "No reasoning summary available.");
  const policyAllowed = state.policy_allowed;
  const toolName = String(run.requested_tool ?? "n/a");

  return (
    <AppShell
      title={`Run Details · #${run.id}`}
      subtitle="Deep dive into graph state, policy decisions, tool activity, and operator controls."
    >
      <section className="metrics-grid">
        <div className="panel">
          <p className="muted small">Run Status</p>
          <div className="row">
            <StatusBadge value={run.status} />
            {["running", "awaiting_human_approval"].includes(run.status) ? <KillRunForm runId={run.id} /> : null}
          </div>
        </div>
        <div className="panel">
          <p className="muted small">Risk Tier</p>
          <div className="row">
            <StatusBadge value={run.risk_label ?? "low"} />
          </div>
        </div>
        <div className="panel">
          <p className="muted small">Requested Tool</p>
          <div className="metric-value small-metric">{toolName}</div>
        </div>
      </section>

      <section className="dashboard-grid">
        <SectionCard title="State Summary">
          <div className="detail-grid">
            <p className="small">
              <strong>Workflow</strong>
              <br />
              {run.workflow_name}
            </p>
            <p className="small">
              <strong>Current Node</strong>
              <br />
              {run.current_node}
            </p>
            <p className="small">
              <strong>Approval Required</strong>
              <br />
              {String(state.approval_required ?? false)}
            </p>
          </div>
        </SectionCard>

        <SectionCard title="Classification">
          <p className="small">
            <strong>Label</strong>
            <br />
            {classification}
          </p>
          <p className="muted small">{reasoning}</p>
        </SectionCard>
      </section>

      <section className="dashboard-grid">
        <SectionCard title="Policy Check Result">
          <div className="stack">
            <p className="small">
              <strong>Allowed</strong>
              <br />
              {String(policyAllowed ?? false)}
            </p>
            <p className="muted small">
              {String(state.policy_violation_reason ?? "Policy passed or no violation recorded.")}
            </p>
          </div>
        </SectionCard>

        <SectionCard title="Tool Calls">
          <div className="stack">
            <ToolPills tools={[toolName]} />
            <div className="detail-grid">
              <p className="small">
                <strong>Executed</strong>
                <br />
                {String(execution.executed ?? false)}
              </p>
              <p className="small">
                <strong>Execution Time</strong>
                <br />
                {String(execution.execution_time_ms ?? "n/a")} ms
              </p>
              <p className="small">
                <strong>Simulated Cost</strong>
                <br />
                ${String(execution.simulated_cost_usd ?? "0.00")}
              </p>
            </div>
          </div>
        </SectionCard>
      </section>

      <SectionCard title="Run Timeline">
        <div className="timeline">
          {events.map((event) => (
            <article key={`${event.event_type}-${event.id}`} className="timeline-item">
              <div className="row">
                <strong>{event.event_type}</strong>
                <StatusBadge value={event.payload?.status ? String(event.payload.status) : event.level} />
              </div>
              <p className="muted small">{event.created_at}</p>
              <p className="small">{event.message}</p>
            </article>
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Graph Transitions">
        <div className="timeline">
          {run.transition_history.map((event, index) => (
            <article key={`${event.node}-${index}`} className="timeline-item">
              <div className="row">
                <strong>{event.node}</strong>
                <StatusBadge value={event.status} />
              </div>
              <p className="muted small">{event.timestamp}</p>
              <p className="small">{event.message}</p>
            </article>
          ))}
        </div>
      </SectionCard>
    </AppShell>
  );
}
