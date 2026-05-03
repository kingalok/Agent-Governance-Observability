LOW_RISK_SAMPLE_PAYLOAD = {
    "request_type": "document_intake",
    "requested_action": "triage_and_route",
    "requested_tool": "create_ticket",
    "requested_by": "operations.analyst",
    "document_title": "Q2 support trend summary",
    "document_text": "Summarize the internal support notes and route a follow-up ticket to the platform backlog.",
    "external_destination": False,
    "contains_pii": False,
}

HIGH_RISK_SAMPLE_PAYLOAD = {
    "request_type": "document_intake",
    "requested_action": "finalize_external_delivery",
    "requested_tool": "send_email",
    "requested_by": "data.operations",
    "document_title": "Customer export request",
    "document_text": "Prepare and send the requested customer data export to the external requester.",
    "external_destination": True,
    "contains_pii": True,
}

POLICY_VIOLATION_SAMPLE_PAYLOAD = {
    "request_type": "document_intake",
    "requested_action": "modify_vendor_record",
    "requested_tool": "update_vendor_record",
    "requested_by": "support.bot",
    "document_title": "Vendor correction request",
    "document_text": "Update the vendor record directly based on the attached request.",
    "external_destination": False,
    "contains_pii": True,
}
