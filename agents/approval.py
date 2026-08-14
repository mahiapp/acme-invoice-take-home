# Approval agent: approve or reject invoices with a reflection step.

import json

from utils import get_llm, parse_llm_json

SYSTEM_PROMPT = """
ROLE
You are the VP-level approval agent for Acme Corp accounts payable.

EXPECTATIONS
- Review every invoice (not only failures or high-dollar ones).
- Invoices >= 10000 need extra scrutiny.
- Lean reject for unknown items, zero-stock/fraud signals, negative qty, or urgent wire-payment language.
- Price mismatch alone is usually not enough to reject.
- Weigh ingestion issues and validation issues together.
- If previously_processed is true, use prior_invoice details to decide whether this submission should replace the earlier record (e.g. a legitimate revision) or be rejected as a duplicate/suspicious resubmission.

ACTION
Return JSON only with:
- decision: "approved" or "rejected"
- reasoning: short explanation
- action: what should happen next (e.g. "pay vendor", "replace prior invoice and pay", or "block payment and notify AP")

CONTEXT
You receive ingestion output plus validation results, including any prior invoice history. Payment is executed only if you approve. An approved revision replaces the stored invoice record.

HANDOFF
Return valid JSON only (no markdown).
"""

CRITIQUE_PROMPT = """
ROLE
You critique draft approval decisions for Acme Corp AP.

EXPECTATIONS
- Check whether the draft ignored $10k scrutiny, fraud/urgent-pay language, stock/unknown-item failures, duplicate/revision handling, or overreacted to a lone price variance.
- Be specific and concise.

ACTION
List weaknesses or missing considerations in the draft. If the draft is sound, say so briefly.

HANDOFF
Plain text critique only; the main approval agent will produce the final JSON.
"""


def approve_invoice(validated_result):
    '''Approve or reject a validated invoice using draft, critique, and final passes.'''
    llm = get_llm()
    invoice = json.dumps(validated_result)

    draft = llm.invoke(
        [("system", SYSTEM_PROMPT), ("user", invoice + "\nReturn JSON only.")]
    ).content

    critique = llm.invoke(
        [
            ("system", CRITIQUE_PROMPT),
            ("user", invoice + "\n\nDraft decision:\n" + draft),
        ]
    ).content

    final = llm.invoke(
        [
            ("system", SYSTEM_PROMPT),
            (
                "user",
                invoice
                + "\n\nDraft:\n"
                + draft
                + "\n\nCritique:\n"
                + critique
                + "\n\nReturn final JSON only with decision, reasoning, action.",
            ),
        ]
    ).content

    out = dict(validated_result)
    out.update(parse_llm_json(final))
    out["draft"] = draft
    out["critique"] = critique
    return out
