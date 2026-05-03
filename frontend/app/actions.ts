"use server";

import { revalidatePath } from "next/cache";

async function postJson(path: string, body?: Record<string, unknown>) {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  const response = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
}

export async function approveRunAction(formData: FormData) {
  const runId = formData.get("runId");
  const reviewerName = formData.get("reviewerName");
  if (!runId || !reviewerName) return;

  await postJson(`/api/v1/approvals/${runId}/approve`, {
    reviewer_name: String(reviewerName),
  });

  revalidatePath("/");
  revalidatePath("/approvals");
  revalidatePath("/runs");
  revalidatePath(`/runs/${runId}`);
}

export async function rejectRunAction(formData: FormData) {
  const runId = formData.get("runId");
  const reviewerName = formData.get("reviewerName");
  const rejectionReason = formData.get("rejectionReason");
  if (!runId || !reviewerName || !rejectionReason) return;

  await postJson(`/api/v1/approvals/${runId}/reject`, {
    reviewer_name: String(reviewerName),
    rejection_reason: String(rejectionReason),
  });

  revalidatePath("/");
  revalidatePath("/approvals");
  revalidatePath("/runs");
  revalidatePath(`/runs/${runId}`);
}

export async function killRunAction(formData: FormData) {
  const runId = formData.get("runId");
  if (!runId) return;

  await postJson(`/api/v1/runs/${runId}/kill`);

  revalidatePath("/");
  revalidatePath("/runs");
  revalidatePath(`/runs/${runId}`);
}
