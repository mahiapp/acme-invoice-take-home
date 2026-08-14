# Terminal logging helpers for pipeline stages and summaries.

import json

from utils import is_approved


def stage(name):
    '''Print a stage banner.'''
    print()
    print("=" * 60)
    print(f" {name}")
    print("=" * 60)


def lines(*lines):
    '''Print indented lines.'''
    print()
    for line in lines:
        print(f"  {line}")
    print()


_lines = lines


def data(obj):
    '''Print a JSON object with indentation.'''
    print(json.dumps(obj, indent=2))


def end(msg):
    '''Print a stage completion message.'''
    print()
    print("-" * 60)
    print(f" {msg}")
    print("-" * 60)


def rollup(result):
    '''Print a summary for a single invoice run.'''
    items = result.get("items") or []
    ing_issues = result.get("issues") or []
    val_issues = result.get("validation_issues") or []
    paid = is_approved(result.get("decision"))

    _lines(
        "RUN SUMMARY",
        f"  Line items:          {len(items)}",
        f"  Ingestion issues:    {len(ing_issues)}",
        f"  Validation issues:   {len(val_issues)}",
        f"  Validation status:   {result.get('validation_status')}",
        f"  Decision:            {result.get('decision')}",
        f"  Payment:             {'submitted' if paid else 'blocked'}",
    )
    if ing_issues:
        _lines("Ingestion issues:", *[f"  - {i}" for i in ing_issues])
    if val_issues:
        _lines("Validation issues:", *[f"  - {i}" for i in val_issues])


def ingestion(result):
    '''Print a short ingestion summary.'''
    items = result.get("items") or []
    issues = result.get("issues") or []
    lines = [
        f"Invoice: {result.get('invoice_number')}",
        f"Vendor:  {result.get('vendor')}",
        f"Due:     {result.get('due_date')}",
        f"Subtotal:{result.get('subtotal')}",
        f"Tax:     {result.get('tax_amount')}",
        f"Shipping:{result.get('shipping')}",
        f"Total:   {result.get('total_amount')}",
        f"Items:   {len(items)}",
    ]
    for item in items:
        lines.append(
            f"  - {item.get('name')}: qty {item.get('quantity')} @ {item.get('unit_price')}"
        )
    lines.append(f"Issues:  {len(issues)}")
    if issues:
        for issue in issues:
            lines.append(f"  - {issue}")
    else:
        lines.append("  - none")
    _lines(*lines)


def validation(result):
    '''Print a short validation summary.'''
    issues = result.get("validation_issues") or []
    lines = [
        f"Status:  {result.get('validation_status')}",
        f"Issues:  {len(issues)}",
    ]
    if issues:
        for issue in issues:
            lines.append(f"  - {issue}")
    else:
        lines.append("  - none")
    _lines(*lines)


def approval(result):
    '''Print a short approval summary.'''
    _lines(
        f"Decision:  {result.get('decision')}",
        f"Action:    {result.get('action')}",
        f"Reasoning: {result.get('reasoning')}",
    )


def batch_rollup(results):
    '''Print aggregate results after a batch run.'''
    approved = []
    rejected = []
    errors = []

    for row in results:
        if row.get("error"):
            errors.append(row)
            continue
        if is_approved(row.get("decision")):
            approved.append(row)
        else:
            rejected.append(row)

    _lines(
        "BATCH SUMMARY",
        f"  Total invoices:   {len(results)}",
        f"  Approved:         {len(approved)}",
        f"  Rejected:         {len(rejected)}",
        f"  Failed to process:{len(errors)}",
    )

    if approved:
        _lines(
            "Approved:",
            *[
                f"  - {r.get('invoice_number')} ({r.get('vendor')}) ${r.get('total_amount')}"
                for r in approved
            ],
        )
    if rejected:
        _lines(
            "Rejected:",
            *[
                f"  - {r.get('invoice_number')} ({r.get('vendor')}): {r.get('reasoning')}"
                for r in rejected
            ],
        )
    if errors:
        _lines("Errors:", *[f"  - {r.get('path')}: {r.get('error')}" for r in errors])

    all_ing = []
    all_val = []
    for r in results:
        if r.get("error"):
            continue
        all_ing.extend(r.get("issues") or [])
        all_val.extend(r.get("validation_issues") or [])

    _lines(
        "ISSUE TOTALS",
        f"  Ingestion issues:  {len(all_ing)}",
        f"  Validation issues: {len(all_val)}",
    )
    if all_ing:
        _lines("Ingestion issues:", *[f"  - {i}" for i in all_ing])
    if all_val:
        _lines("Validation issues:", *[f"  - {i}" for i in all_val])
