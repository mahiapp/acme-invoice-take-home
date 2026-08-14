# CLI entry point and LangGraph orchestration for the invoice pipeline.

import argparse
import os
from typing import TypedDict

from langgraph.graph import END, StateGraph

import logs
from agents.approval import approve_invoice
from agents.ingestion import ingest_invoice
from agents.validation import validate_invoice
from data.db_read import attach_prior_invoice, record_invoice
from utils import is_approved


# Shared state passed between LangGraph nodes.
class State(TypedDict):
    path: str
    data: dict


def mock_payment(vendor, amount):
    '''Simulate a payment API call for an approved invoice.'''
    print(f"Paid {amount} to {vendor}")
    return {"status": "success"}


def list_invoices(path):
    '''Return a list of invoice file paths from a file or directory.'''
    if os.path.isfile(path):
        return [path]
    return [
        os.path.join(path, name)
        for name in sorted(os.listdir(path))
        if os.path.isfile(os.path.join(path, name)) and not name.startswith(".")
    ]


def ingestion_node(state: State):
    '''Run the ingestion agent and update graph state.'''
    path = state["path"]
    logs.stage(f"INGESTION - {os.path.basename(path)}")
    data = ingest_invoice(path)
    data = attach_prior_invoice(data)
    logs.ingestion(data)
    return {"data": data}


def validation_node(state: State):
    '''Run the validation agent and update graph state.'''
    path = state["path"]
    logs.stage(f"VALIDATION - {os.path.basename(path)}")
    data = validate_invoice(state["data"])
    logs.validation(data)
    return {"data": data}


def approval_node(state: State):
    '''Run the approval agent and update graph state.'''
    path = state["path"]
    logs.stage(f"APPROVAL - {os.path.basename(path)}")
    data = approve_invoice(state["data"])
    logs.approval(data)
    return {"data": data}


# Pipeline: ingestion -> validation -> approval. Payment runs after the graph.
graph = StateGraph(State)
graph.add_node("ingestion", ingestion_node)
graph.add_node("validation", validation_node)
graph.add_node("approval", approval_node)
graph.set_entry_point("ingestion")
graph.add_edge("ingestion", "validation")
graph.add_edge("validation", "approval")
graph.add_edge("approval", END)
app = graph.compile()


def main():
    '''Run the invoice pipeline from the command line.'''
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--invoice_path",
        required=True,
        help="Path to one invoice file (required). Pass a folder to run batch mode.",
    )
    args = parser.parse_args()

    if not os.path.exists(args.invoice_path):
        raise SystemExit(f"Invoice path not found: {args.invoice_path}")

    paths = list_invoices(args.invoice_path)
    batch = len(paths) > 1 or os.path.isdir(args.invoice_path)

    if batch:
        logs.stage(f"BATCH - {len(paths)} invoice(s)")
        logs.lines(*[os.path.basename(p) for p in paths])

    results = []
    for path in paths:
        try:
            final = app.invoke({"path": path, "data": {}})
            result = dict(final["data"])
            result["path"] = path

            logs.stage(f"PAYMENT - {os.path.basename(path)}")
            if is_approved(result.get("decision")):
                mock_payment(result.get("vendor"), result.get("total_amount"))
                logs.end(f"{result.get('invoice_number')} - payment submitted")
            else:
                print(f"Rejected: {result.get('reasoning')}")
                logs.end(f"{result.get('invoice_number')} - payment blocked")

            record_invoice(result, path)
            results.append(result)
        except Exception as e:
            logs.end(f"ERROR - {os.path.basename(path)}: {e}")
            results.append({"path": path, "error": str(e)})

    if batch:
        logs.batch_rollup(results)
        logs.end("BATCH COMPLETE")
    elif results and not results[0].get("error"):
        logs.rollup(results[0])


if __name__ == "__main__":
    main()
