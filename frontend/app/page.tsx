type DashboardSummary = {
  total_agents: number;
  active_agents: number;
  paused_agents: number;
  killed_agents: number;
  pending_approvals: number;
  high_risk_agents: number;
};

type Agent = {
  id: number;
  name: string;
  description: string;
  owner_name: string;
  team_name: string;
  risk_tier: "low" | "medium" | "high";
  status: "active" | "paused" | "killed";
  is_kill_switched: boolean;
  allowed_tools: string[];
  model_name: string;
};

type RuntimeLog = {
  id: number;
  workflow_name: string;
  event_type: string;
  level: "info" | "warning" | "error";
  message: string;
  created_at: string;
};

type Approval = {
  id: number;
  workflow_name: string;
  action_name: string;
  reason: string;
  status: "pending" | "approved" | "rejected";
  created_at: string;
};

const fallbackSummary: DashboardSummary = {
  total_agents: 3,
  active_agents: 3,
  paused_agents: 0,
  killed_agents: 0,
  pending_approvals: 1,
  high_risk_agents: 1,
};

const fallbackAgents: Agent[] = [
  {
    id: 1,
    name: "Vendor Risk Copilot",
    description: "Reviews third-party vendor requests and flags governance concerns.",
    owner_name: "Priya Shah",
    team_name: "Security Engineering",
    risk_tier: "medium",
    status: "active",
    is_kill_switched: false,
    allowed_tools: ["slack_notify", "ticket_lookup", "policy_search"],
    model_name: "gpt-4.1",
  },
  {
    id: 2,
    name: "PII Export Agent",
    description: "Coordinates regulated customer data export requests with approval controls.",
    owner_name: "Marcus Lee",
    team_name: "Data Platform",
    risk_tier: "high",
    status: "active",
    is_kill_switched: false,
    allowed_tools: ["warehouse_query", "export_package", "email_notify"],
    model_name: "gpt-4.1",
  },
  {
    id: 3,
    name: "Knowledge Base Curator",
    description: "Maintains internal knowledge summaries for go-to-market teams.",
    owner_name: "Hannah Brooks",
    team_name: "Revenue Operations",
    risk_tier: "low",
    status: "active",
    is_kill_switched: false,
    allowed_tools: ["docs_search", "cms_publish"],
    model_name: "gpt-4.1-mini",
  },
];

const fallbackLogs: RuntimeLog[] = [
  {
    id: 1,
    workflow_name: "regulated_export",
    event_type: "approval_requested",
    level: "warning",
    message: "High-risk export requires human approval before release.",
    created_at: new Date().toISOString(),
  },
  {
    id: 2,
    workflow_name: "vendor_review",
    event_type: "policy_scan_completed",
    level: "info",
    message: "Policy evaluation completed without escalation.",
    created_at: new Date().toISOString(),
  },
];

const fallbackApprovals: Approval[] = [
  {
    id: 1,
    workflow_name: "regulated_export",
    action_name: "release_customer_export",
    reason: "Customer data export exceeds automatic approval threshold.",
    status: "pending",
    created_at: new Date().toISOString(),
  },
];

async function fetchJson<T>(path: string, fallback: T): Promise<T> {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

  try {
    const response = await fetch(`${baseUrl}${path}`, {
      next: { revalidate: 0 },
    });

    if (!response.ok) {
      return fallback;
    }

    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

export default async function HomePage() {
  const [summary, agents, logs, approvals] = await Promise.all([
    fetchJson<DashboardSummary>("/api/v1/observability/summary", fallbackSummary),
    fetchJson<Agent[]>("/api/v1/agents", fallbackAgents),
    fetchJson<RuntimeLog[]>("/api/v1/observability/logs", fallbackLogs),
    fetchJson<Approval[]>("/api/v1/agents/approvals", fallbackApprovals),
  ]);

  return (
    <main className="page-shell">
      <section className="hero">
        <span className="eyebrow">CTO Portfolio Demo</span>
        <div className="hero-grid">
          <div className="stack">
            <h1>Govern AI agents like production software.</h1>
            <p>
              This proof of concept shows how agent inventory, ownership, runtime logs, approval
              gates, and operational controls can live in one clean governance layer.
            </p>
          </div>
          <div className="panel">
            <p className="muted small">Enterprise workflow demo</p>
            <h2 className="section-title">Regulated Data Export</h2>
            <p className="muted">
              High-risk actions route through a LangGraph approval checkpoint before execution, with
              observability events written to SQLite and tracing hooks ready for LangSmith.
            </p>
          </div>
        </div>
      </section>

      <section className="metrics-grid">
        <div className="panel">
          <p className="muted small">Registered Agents</p>
          <div className="metric-value">{summary.total_agents}</div>
        </div>
        <div className="panel">
          <p className="muted small">Active</p>
          <div className="metric-value">{summary.active_agents}</div>
        </div>
        <div className="panel">
          <p className="muted small">High Risk</p>
          <div className="metric-value">{summary.high_risk_agents}</div>
        </div>
        <div className="panel">
          <p className="muted small">Pending Approvals</p>
          <div className="metric-value">{summary.pending_approvals}</div>
        </div>
      </section>

      <section className="content-grid">
        <div className="panel">
          <h2 className="section-title">Agent Registry</h2>
          <div className="stack">
            {agents.map((agent) => (
              <article key={agent.id} className="agent-card">
                <div className="topline">
                  <span className={`badge ${agent.risk_tier}`}>{agent.risk_tier} risk</span>
                  <span className={`badge ${agent.status}`}>{agent.status}</span>
                </div>
                <h3>{agent.name}</h3>
                <p className="muted">{agent.description}</p>
                <p className="small">
                  <strong>Owner:</strong> {agent.owner_name} · <strong>Team:</strong> {agent.team_name}
                </p>
                <p className="small">
                  <strong>Model:</strong> {agent.model_name} · <strong>Kill switch:</strong>{" "}
                  {agent.is_kill_switched ? "enabled" : "ready"}
                </p>
                <div className="tool-list">
                  {agent.allowed_tools.map((tool) => (
                    <span key={tool} className="tool-pill">
                      {tool}
                    </span>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </div>

        <div className="stack">
          <section className="panel">
            <h2 className="section-title">Approval Queue</h2>
            <div className="timeline">
              {approvals.map((approval) => (
                <article key={approval.id} className="approval-card">
                  <div className="row">
                    <strong>{approval.action_name}</strong>
                    <span className={`badge ${approval.status}`}>{approval.status}</span>
                  </div>
                  <p className="muted small">{approval.workflow_name}</p>
                  <p className="small">{approval.reason}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="panel">
            <h2 className="section-title">Runtime Events</h2>
            <div className="timeline">
              {logs.slice(0, 5).map((log) => (
                <article key={log.id} className="log-card">
                  <div className="row">
                    <strong>{log.event_type}</strong>
                    <span className={`badge ${log.level}`}>{log.level}</span>
                  </div>
                  <p className="muted small">{log.workflow_name}</p>
                  <p className="small">{log.message}</p>
                </article>
              ))}
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}
