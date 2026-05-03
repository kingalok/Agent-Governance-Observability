import { AppShell } from "../../components/app-shell";
import { SectionCard, StatusBadge, ToolPills } from "../../components/dashboard-primitives";
import { getAgents } from "../../lib/dashboard";

export default async function AgentsPage() {
  const agents = await getAgents();

  return (
    <AppShell
      title="Agent Registry"
      subtitle="Inventory of governed agents, business ownership, risk classification, and approved tool surfaces."
    >
      <SectionCard title="Registered Agents">
        <div className="stack">
          {agents.map((agent) => (
            <article key={agent.id} className="agent-card expanded">
              <div className="topline">
                <div className="row start">
                  <StatusBadge value={agent.risk_tier ?? "low"} />
                  <StatusBadge value={agent.status} />
                </div>
                <span className="muted small">{agent.model_name}</span>
              </div>
              <h3>{agent.name}</h3>
              <p className="muted">{agent.description}</p>
              <div className="detail-grid">
                <p className="small">
                  <strong>Owner</strong>
                  <br />
                  {agent.owner_name}
                </p>
                <p className="small">
                  <strong>Team</strong>
                  <br />
                  {agent.team_name}
                </p>
                <p className="small">
                  <strong>Kill Switch</strong>
                  <br />
                  {agent.is_kill_switched ? "Enabled" : "Ready"}
                </p>
              </div>
              <ToolPills tools={agent.allowed_tools ?? []} />
            </article>
          ))}
        </div>
      </SectionCard>
    </AppShell>
  );
}
