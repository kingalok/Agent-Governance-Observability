export type Agent = {
  id: number;
  name: string;
  description: string;
  owner_name?: string;
  team_name?: string;
  owner?: string;
  team?: string;
  risk_tier?: "low" | "medium" | "high";
  default_risk_tier?: "low" | "medium" | "high";
  status: "active" | "paused" | "killed";
  is_kill_switched: boolean;
  allowed_tools?: string[];
  model_name: string;
};

export type Approval = {
  id: number;
  run_id: number | null;
  workflow_name: string;
  action_name: string;
  reason: string;
  status: "pending" | "approved" | "rejected";
  requested_by: string;
  decided_by?: string | null;
  rejection_reason?: string | null;
  created_at: string;
  decided_at?: string | null;
};

export type RunSummary = {
  run_id: number;
  agent_id: number;
  workflow_name: string;
  agent_name: string;
  status:
    | "pending"
    | "running"
    | "awaiting_human_approval"
    | "success"
    | "failed"
    | "policy_violation"
    | "stopped";
  current_node: string;
  state: string;
  graph_state: Record<string, unknown>;
  risk_tier: "low" | "medium" | "high";
  requested_tool?: string | null;
  approval_required: boolean;
  message: string;
};

export type RunDetail = {
  id: number;
  agent_id: number;
  workflow_name: string;
  request_type: string;
  requested_tool?: string | null;
  status: RunSummary["status"];
  current_node: string;
  input_payload: Record<string, unknown>;
  state_payload: Record<string, unknown>;
  transition_history: Array<{
    node: string;
    status: string;
    timestamp: string;
    message: string;
  }>;
  classification_label?: string | null;
  risk_label?: "low" | "medium" | "high" | null;
  reasoning_summary?: string | null;
  final_output: Record<string, unknown>;
  graph_state: Record<string, unknown>;
  started_at: string;
  updated_at: string;
  completed_at?: string | null;
};

export type RuntimeEvent = {
  id: number;
  event_type: string;
  level: "info" | "warning" | "error";
  message: string;
  payload?: Record<string, unknown>;
  created_at: string;
  workflow_name?: string;
};

export type DashboardSummary = {
  total_runs: number;
  pending_approvals: number;
  successful_runs: number;
  blocked_runs: number;
  simulated_input_tokens: number;
  simulated_output_tokens: number;
  simulated_cost_usd: number;
  total_agents: number;
};

const fallbackNow = new Date().toISOString();

export const fallbackAgents: Agent[] = [
  {
    id: 1,
    name: "Knowledge Base Curator",
    description: "Maintains internal knowledge summaries for go-to-market teams.",
    owner_name: "Hannah Brooks",
    team_name: "Revenue Operations",
    risk_tier: "low",
    status: "active",
    is_kill_switched: false,
    allowed_tools: ["create_ticket"],
    model_name: "gpt-4.1-mini",
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
    allowed_tools: ["send_email", "update_vendor_record"],
    model_name: "gpt-4.1",
  },
];

export const fallbackRuns: RunSummary[] = [
  {
    run_id: 1,
    agent_id: 1,
    workflow_name: "document_governance_workflow",
    agent_name: "Knowledge Base Curator",
    status: "success",
    current_node: "finalize_node",
    state: "success",
    graph_state: {
      classification_label: "internal_operations_request",
      reasoning_summary: "Marked medium risk because the action writes to an internal system.",
      policy_allowed: true,
      execution_result: {
        tool: "create_ticket",
        allowed: true,
        executed: true,
        execution_time_ms: 1.2,
        simulated_cost_usd: 0.01,
      },
    },
    risk_tier: "medium",
    requested_tool: "create_ticket",
    approval_required: false,
    message: "Tool 'create_ticket' executed in demo mode.",
  },
  {
    run_id: 2,
    agent_id: 2,
    workflow_name: "document_governance_workflow",
    agent_name: "PII Export Agent",
    status: "awaiting_human_approval",
    current_node: "approval_gate_node",
    state: "awaiting_human_approval",
    graph_state: {
      classification_label: "sensitive_document_request",
      reasoning_summary: "Flagged as high risk because the request appears to expose regulated data.",
      policy_allowed: true,
      approval_required: true,
    },
    risk_tier: "high",
    requested_tool: "send_email",
    approval_required: true,
    message: "Workflow paused for human approval.",
  },
  {
    run_id: 3,
    agent_id: 2,
    workflow_name: "document_governance_workflow",
    agent_name: "PII Export Agent",
    status: "policy_violation",
    current_node: "finalize_node",
    state: "policy_violation",
    graph_state: {
      policy_violation_reason: "Tool 'update_vendor_record' is not allowed for agent 'PII Export Agent'.",
    },
    risk_tier: "high",
    requested_tool: "update_vendor_record",
    approval_required: true,
    message: "Policy violation blocked the requested action.",
  },
];

export const fallbackApprovals: Approval[] = [
  {
    id: 1,
    run_id: 2,
    workflow_name: "document_governance_workflow",
    action_name: "finalize_external_delivery",
    reason: "Customer data export exceeds the automatic approval threshold.",
    status: "pending",
    requested_by: "workflow-engine",
    created_at: fallbackNow,
  },
];

export const fallbackLogs: RuntimeEvent[] = [
  {
    id: 1,
    workflow_name: "document_governance_workflow",
    event_type: "approval_requested",
    level: "warning",
    message: "High-risk export requires human approval before release.",
    created_at: fallbackNow,
    payload: { approval_required: true },
  },
  {
    id: 2,
    workflow_name: "document_governance_workflow",
    event_type: "tool_call_audit",
    level: "info",
    message: "Tool 'create_ticket' executed under governance controls.",
    created_at: fallbackNow,
    payload: { tool: "create_ticket", simulated_cost_usd: 0.01 },
  },
];

export const fallbackRunDetails: Record<number, RunDetail> = {
  1: {
    id: 1,
    agent_id: 1,
    workflow_name: "document_governance_workflow",
    request_type: "document_intake",
    requested_tool: "create_ticket",
    status: "success",
    current_node: "finalize_node",
    input_payload: {
      request_type: "document_intake",
      requested_action: "triage_and_route",
      requested_tool: "create_ticket",
    },
    state_payload: fallbackRuns[0].graph_state,
    transition_history: [
      { node: "intake_node", status: "running", timestamp: fallbackNow, message: "Request intake completed." },
      { node: "classification_node", status: "running", timestamp: fallbackNow, message: "Task classified and risk-labeled." },
      { node: "policy_check_node", status: "running", timestamp: fallbackNow, message: "Policy check passed." },
      { node: "tool_execution_node", status: "running", timestamp: fallbackNow, message: "Tool 'create_ticket' executed in demo mode." },
      { node: "finalize_node", status: "success", timestamp: fallbackNow, message: "Workflow finalized." },
    ],
    classification_label: "internal_operations_request",
    risk_label: "medium",
    reasoning_summary: "Marked medium risk because the action writes to an internal system.",
    final_output: {
      execution_result: {
        tool: "create_ticket",
        allowed: true,
        executed: true,
        execution_time_ms: 1.2,
        simulated_cost_usd: 0.01,
        details: { ticket_id: "TKT-0001", queue: "platform-ops" },
      },
    },
    graph_state: fallbackRuns[0].graph_state,
    started_at: fallbackNow,
    updated_at: fallbackNow,
    completed_at: fallbackNow,
  },
  2: {
    id: 2,
    agent_id: 2,
    workflow_name: "document_governance_workflow",
    request_type: "document_intake",
    requested_tool: "send_email",
    status: "awaiting_human_approval",
    current_node: "approval_gate_node",
    input_payload: {
      request_type: "document_intake",
      requested_action: "finalize_external_delivery",
      requested_tool: "send_email",
    },
    state_payload: fallbackRuns[1].graph_state,
    transition_history: [
      { node: "intake_node", status: "running", timestamp: fallbackNow, message: "Request intake completed." },
      { node: "classification_node", status: "running", timestamp: fallbackNow, message: "Task classified and risk-labeled." },
      { node: "policy_check_node", status: "running", timestamp: fallbackNow, message: "Policy check passed." },
      { node: "approval_gate_node", status: "awaiting_human_approval", timestamp: fallbackNow, message: "Workflow paused for human approval." },
    ],
    classification_label: "sensitive_document_request",
    risk_label: "high",
    reasoning_summary: "Flagged as high risk because the request appears to expose regulated data.",
    final_output: {},
    graph_state: fallbackRuns[1].graph_state,
    started_at: fallbackNow,
    updated_at: fallbackNow,
    completed_at: null,
  },
};

async function fetchJson<T>(path: string, fallback: T): Promise<T> {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

  try {
    const response = await fetch(`${baseUrl}${path}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return fallback;
    }

    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

export async function getAgents(): Promise<Agent[]> {
  const agents = await fetchJson<Agent[]>("/api/v1/agents", fallbackAgents);
  return agents.map((agent) => ({
    ...agent,
    owner_name: agent.owner_name ?? agent.owner ?? "Unknown Owner",
    team_name: agent.team_name ?? agent.team ?? "Unknown Team",
    risk_tier: agent.risk_tier ?? agent.default_risk_tier ?? "low",
    allowed_tools: agent.allowed_tools ?? [],
  }));
}

export async function getRuns(): Promise<RunSummary[]> {
  return fetchJson<RunSummary[]>("/api/v1/runs", fallbackRuns);
}

export async function getPendingApprovals(): Promise<Approval[]> {
  return fetchJson<Approval[]>("/api/v1/approvals/pending", fallbackApprovals);
}

export async function getLogs(): Promise<RuntimeEvent[]> {
  return fetchJson<RuntimeEvent[]>("/api/v1/observability/logs", fallbackLogs);
}

export async function getRunEvents(id: number): Promise<RuntimeEvent[]> {
  const fallbackEvents: RuntimeEvent[] =
    fallbackRunDetails[id]?.transition_history.map((event, index) => ({
      id: index + 1,
      event_type: event.node,
      level:
        event.status === "awaiting_human_approval"
          ? "warning"
          : event.status === "failed"
            ? "error"
            : "info",
      message: event.message,
      created_at: event.timestamp,
      payload: { status: event.status },
      workflow_name: fallbackRunDetails[id]?.workflow_name,
    })) ?? fallbackLogs;

  return fetchJson<RuntimeEvent[]>(`/api/v1/runs/${id}/events`, fallbackEvents);
}

export async function getRunDetail(id: number): Promise<RunDetail> {
  return fetchJson<RunDetail>(`/api/v1/runs/${id}`, fallbackRunDetails[id] ?? fallbackRunDetails[1]);
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const [agents, runs, approvals] = await Promise.all([getAgents(), getRuns(), getPendingApprovals()]);
  const successfulRuns = runs.filter((run) => run.status === "success").length;
  const blockedRuns = runs.filter((run) => ["policy_violation", "failed", "stopped"].includes(run.status)).length;

  const totals = runs.reduce(
    (acc, run) => {
      const execution = (run.graph_state.execution_result ?? {}) as Record<string, unknown>;
      acc.input += Number((run.graph_state.input_tokens as number | undefined) ?? 0);
      acc.output += Number((run.graph_state.output_tokens as number | undefined) ?? 0);
      acc.cost += Number((execution.simulated_cost_usd as number | undefined) ?? 0);
      return acc;
    },
    { input: 0, output: 0, cost: 0 },
  );

  return {
    total_runs: runs.length,
    pending_approvals: approvals.length,
    successful_runs: successfulRuns,
    blocked_runs: blockedRuns,
    simulated_input_tokens: totals.input || 6900,
    simulated_output_tokens: totals.output || 1490,
    simulated_cost_usd: Number((totals.cost || 0.57).toFixed(2)),
    total_agents: agents.length,
  };
}

export function getStatusTone(status: string): string {
  if (["success", "active", "approved"].includes(status)) return "success";
  if (["awaiting_human_approval", "pending", "paused", "medium"].includes(status)) return "warning";
  if (["policy_violation", "failed", "stopped", "rejected", "killed", "high"].includes(status)) return "danger";
  return "neutral";
}
