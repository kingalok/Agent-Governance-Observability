"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import type { Agent, RunSummary } from "../lib/dashboard";
import { getStatusTone } from "../lib/dashboard";

export function RunExplorerClient({
  runs,
  agents,
}: {
  runs: RunSummary[];
  agents: Agent[];
}) {
  const [statusFilter, setStatusFilter] = useState("all");
  const [riskFilter, setRiskFilter] = useState("all");
  const [agentFilter, setAgentFilter] = useState("all");

  const filteredRuns = useMemo(() => {
    return runs.filter((run) => {
      const statusMatch = statusFilter === "all" || run.status === statusFilter;
      const riskMatch = riskFilter === "all" || run.risk_tier === riskFilter;
      const agentMatch = agentFilter === "all" || String(run.agent_id) === agentFilter;
      return statusMatch && riskMatch && agentMatch;
    });
  }, [agentFilter, riskFilter, runs, statusFilter]);

  return (
    <div className="stack">
      <div className="filter-bar">
        <select className="field select" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="all">All statuses</option>
          <option value="success">Success</option>
          <option value="awaiting_human_approval">Pending approval</option>
          <option value="policy_violation">Blocked</option>
          <option value="stopped">Stopped</option>
        </select>
        <select className="field select" value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)}>
          <option value="all">All risks</option>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
        </select>
        <select className="field select" value={agentFilter} onChange={(e) => setAgentFilter(e.target.value)}>
          <option value="all">All agents</option>
          {agents.map((agent) => (
            <option key={agent.id} value={String(agent.id)}>
              {agent.name}
            </option>
          ))}
        </select>
      </div>

      <div className="table-card">
        <div className="table-header table-grid runs-grid">
          <span>Run</span>
          <span>Agent</span>
          <span>Risk</span>
          <span>Status</span>
          <span>Tool</span>
          <span>Timeline</span>
        </div>
        {filteredRuns.map((run) => (
          <div key={run.run_id} className="table-row table-grid runs-grid">
            <strong>#{run.run_id}</strong>
            <span>{run.agent_name}</span>
            <span className={`badge ${getStatusTone(run.risk_tier)}`}>{run.risk_tier}</span>
            <span className={`badge ${getStatusTone(run.status)}`}>{run.status.replaceAll("_", " ")}</span>
            <span>{run.requested_tool ?? "n/a"}</span>
            <Link href={`/runs/${run.run_id}`} className="text-link">
              View details
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
