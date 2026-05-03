import Link from "next/link";

import { AppShell } from "../../components/app-shell";
import { ApprovalForm } from "../../components/approval-form";
import { EmptyState, SectionCard, StatusBadge } from "../../components/dashboard-primitives";
import { getPendingApprovals } from "../../lib/dashboard";

export default async function ApprovalsPage() {
  const approvals = await getPendingApprovals();

  return (
    <AppShell
      title="Approval Queue"
      subtitle="High-risk runs waiting for reviewer action before governed execution can continue."
    >
      <SectionCard title="Pending Approvals">
        {approvals.length === 0 ? (
          <EmptyState
            title="No approvals waiting"
            description="The queue is clear. New high-risk runs will appear here when approval is required."
          />
        ) : (
          <div className="stack">
            {approvals.map((approval) => (
              <article key={approval.id} className="approval-card expanded">
                <div className="topline">
                  <div className="row start">
                    <strong>Run #{approval.run_id}</strong>
                    <StatusBadge value={approval.status} />
                  </div>
                  {approval.run_id ? (
                    <Link href={`/runs/${approval.run_id}`} className="text-link">
                      Open run
                    </Link>
                  ) : null}
                </div>
                <h3>{approval.action_name}</h3>
                <p className="muted small">{approval.workflow_name}</p>
                <p className="small">{approval.reason}</p>
                {approval.run_id ? <ApprovalForm runId={approval.run_id} /> : null}
              </article>
            ))}
          </div>
        )}
      </SectionCard>
    </AppShell>
  );
}
