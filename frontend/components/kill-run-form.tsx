import { killRunAction } from "../app/actions";

export function KillRunForm({ runId }: { runId: number }) {
  return (
    <form action={killRunAction}>
      <input type="hidden" name="runId" value={runId} />
      <button type="submit" className="button danger subtle">
        Kill Run
      </button>
    </form>
  );
}
