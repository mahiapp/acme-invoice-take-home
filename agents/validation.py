# Validation agent: check extracted invoice data against inventory.

import json

from data.db_read import get_item, get_invoice
from utils import get_llm, parse_llm_json

SYSTEM_PROMPT = """
ROLE
You are the invoice validation agent for Acme Corp. You check ingested invoice data against Acme's inventory source of truth and invoice history.

EXPECTATIONS
- Do not approve or reject payment; only validate and flag issues.
- Trust the provided tool_results for inventory, prior-invoice, and math facts; do not invent stock levels.
- Use base_item when present (e.g. "WidgetA" from "WidgetA (rush order)"); otherwise use name.
- Inventory lookups may resolve spaced/typo variants (e.g. "Widget A" -> "WidgetA") via tool_results.catalog_name. Treat those as found, not unknown.
- Price mismatches are flags, not automatic failures (rush/discount can be legitimate).
- Negative quantities are data-integrity issues.
- Unknown items, zero stock, and quantity above stock must be flagged.
- If a prior invoice exists, flag it as a duplicate/revision for approval to review.
- total_amount may include tax and shipping. Use tool_results.expected_total (line subtotal + tax + shipping) when checking the claimed total. Do not fail just because total_amount differs from line items alone when tax/shipping explain the difference.

ACTION
Given the invoice JSON and tool_results:
1) Review each inventory lookup, prior-invoice lookup, and subtotal check.
2) Return JSON only with:
   - validation_status: "pass" | "fail" | "review"
   - validation_issues: [string, ...]

CONTEXT
Inventory is a static snapshot. tool_results come from deterministic SQLite/math helpers. Ingestion issues describe invoice quality; your issues describe disagreement with internal inventory, pricing, math, or prior invoice history.

HANDOFF
Return valid JSON only (no markdown). Downstream approval will decide whether issues are acceptable and whether a revised invoice should replace a prior one.
"""


def _gather_tool_results(ingestion_result):
    '''Run inventory, prior-invoice, and math checks in Python.'''
    item_lookups = []
    for item in ingestion_result.get("items") or []:
        name = item.get("base_item") or item.get("name")
        row = get_item(name)
        if row is None:
            item_lookups.append(
                {
                    "item": name,
                    "quantity": item.get("quantity"),
                    "unit_price": item.get("unit_price"),
                    "result": "not found",
                }
            )
        else:
            catalog_name, stock, expected_price = row
            item_lookups.append(
                {
                    "item": name,
                    "catalog_name": catalog_name,
                    "quantity": item.get("quantity"),
                    "unit_price": item.get("unit_price"),
                    "stock": stock,
                    "expected_unit_price": expected_price,
                    "result": "found",
                }
            )

    prior = get_invoice(ingestion_result.get("invoice_number"))
    items = ingestion_result.get("items") or []
    line_subtotal = sum(
        float(i.get("quantity") or 0) * float(i.get("unit_price") or 0) for i in items
    )
    tax = float(ingestion_result.get("tax_amount") or 0)
    shipping = float(ingestion_result.get("shipping") or 0)
    expected_total = line_subtotal + tax + shipping
    claimed = ingestion_result.get("total_amount")

    return {
        "item_lookups": item_lookups,
        "prior_invoice": prior,
        "line_items_subtotal": line_subtotal,
        "tax_amount": tax,
        "shipping": shipping,
        "expected_total": expected_total,
        "claimed_total_amount": claimed,
        "expected_total_matches_claimed": (
            None if claimed is None else abs(expected_total - float(claimed)) < 0.01
        ),
    }


def validate_invoice(ingestion_result):
    '''Validate an ingested invoice against inventory using tools + Grok.'''
    tool_results = _gather_tool_results(ingestion_result)
    payload = {
        "invoice": ingestion_result,
        "tool_results": tool_results,
    }
    response = get_llm().invoke(
        [
            ("system", SYSTEM_PROMPT),
            (
                "user",
                json.dumps(payload)
                + "\nReturn JSON only with validation_status and validation_issues.",
            ),
        ]
    )
    out = dict(ingestion_result)
    out.update(parse_llm_json(response.content))
    out["tool_results"] = tool_results
    return out
