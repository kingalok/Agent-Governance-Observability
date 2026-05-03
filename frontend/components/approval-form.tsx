import { approveRunAction, rejectRunAction } from "../app/actions";

export function ApprovalForm({ runId }: { runId: number }) {
  return (
    <div className="approval-actions">
      <form action={approveRunAction} className="approval-form">
        <input type="hidden" name="runId" value={runId} />
        <input name="reviewerName" placeholder="Reviewer name" className="field" required />
        <button type="submit" className="button success">
          Approve
        </button>
      </form>
      <form action={rejectRunAction} className="approval-form reject">
        <input type="hidden" name="runId" value={runId} />
        <input name="reviewerName" placeholder="Reviewer name" className="field" required />
        <input name="rejectionReason" placeholder="Reviewer note" className="field" required />
        <button type="submit" className="button danger">
          Reject
        </button>
      </form>
    </div>
  );
}
