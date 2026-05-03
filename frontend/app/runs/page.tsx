import { AppShell } from "../../components/app-shell";
import { SectionCard } from "../../components/dashboard-primitives";
import { RunExplorerClient } from "../../components/run-explorer-client";
import { getAgents, getRuns } from "../../lib/dashboard";

export default async function RunsPage() {
  const [runs, agents] = await Promise.all([getRuns(), getAgents()]);

  return (
    <AppShell
      title="Run Explorer"
      subtitle="Operational console for workflow runs, filters, status inspection, and timeline drill-down."
    >
      <SectionCard title="Run Inventory">
        <RunExplorerClient runs={runs} agents={agents} />
      </SectionCard>
    </AppShell>
  );
}
