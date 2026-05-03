from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langsmith import traceable

from app.config import get_settings
from app.models import RiskTier


@dataclass
class ClassificationResult:
    label: str
    summary: str
    risk_tier: RiskTier
    reasoning_summary: str


PROMPT_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You classify enterprise document-handling requests for governance. "
            "Return strict JSON with keys: label, summary, risk_tier, reasoning_summary.",
        ),
        (
            "human",
            "Request type: {request_type}\nRequested action: {requested_action}\nRequested tool: {requested_tool}\n"
            "Payload: {payload_json}",
        ),
    ]
)


class GovernanceTaskClassifier:
    def __init__(self) -> None:
        self.settings = get_settings()

    @traceable(run_type="chain", name="task-classification")
    def classify(self, payload: dict[str, Any]) -> ClassificationResult:
        if self.settings.openai_api_key:
            try:
                return self._classify_with_openai(payload)
            except Exception:
                # Demo-safe fallback keeps the workflow usable without external services.
                return self._classify_with_rules(payload)
        return self._classify_with_rules(payload)

    @traceable(run_type="llm", name="task-classification-openai")
    def _classify_with_openai(self, payload: dict[str, Any]) -> ClassificationResult:
        llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.0, api_key=self.settings.openai_api_key)
        prompt = PROMPT_TEMPLATE.invoke(
            {
                "request_type": payload.get("request_type", "document_intake"),
                "requested_action": payload.get("requested_action", "review_document"),
                "requested_tool": payload.get("requested_tool", ""),
                "payload_json": json.dumps(payload, sort_keys=True),
            }
        )
        response = llm.invoke(prompt)
        content = response.content if isinstance(response.content, str) else "".join(str(item) for item in response.content)
        parsed = json.loads(content)

        return ClassificationResult(
            label=str(parsed["label"]),
            summary=str(parsed["summary"]),
            risk_tier=RiskTier(str(parsed["risk_tier"])),
            reasoning_summary=str(parsed["reasoning_summary"]),
        )

    @traceable(run_type="chain", name="task-classification-rules")
    def _classify_with_rules(self, payload: dict[str, Any]) -> ClassificationResult:
        text = " ".join(
            str(payload.get(key, "")) for key in ["document_title", "document_text", "requested_action", "request_type"]
        ).lower()
        requested_tool = str(payload.get("requested_tool", "")).lower()
        contains_external = bool(payload.get("external_destination", False))
        contains_sensitive_data = bool(payload.get("contains_pii", False)) or any(
            keyword in text
            for keyword in ["pii", "customer data", "export", "external", "financial", "contract", "legal hold"]
        )

        if contains_sensitive_data or contains_external or requested_tool in {"send_email", "update_vendor_record"}:
            return ClassificationResult(
                label="sensitive_document_request",
                summary="Request involves potentially sensitive data handling or an outward-facing action.",
                risk_tier=RiskTier.HIGH,
                reasoning_summary="Flagged as high risk because the request appears to expose regulated data or perform a sensitive external change.",
            )

        if "ticket" in text or requested_tool == "create_ticket":
            return ClassificationResult(
                label="internal_operations_request",
                summary="Request appears to be an internal operations workflow with bounded impact.",
                risk_tier=RiskTier.MEDIUM,
                reasoning_summary="Marked medium risk because the action writes to an internal system but does not appear to cross an external trust boundary.",
            )

        return ClassificationResult(
            label="internal_document_review",
            summary="Request is an internal review or classification task with limited operational impact.",
            risk_tier=RiskTier.LOW,
            reasoning_summary="Marked low risk because the task is read-heavy and does not indicate an external side effect.",
        )
