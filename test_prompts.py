# Prompt testing helper - run one stage or the full agent chain without payment.

import argparse
import os

import logs
from agents.approval import approve_invoice
from agents.ingestion import ingest_invoice
from agents.validation import validate_invoice
from data.db_read import attach_prior_invoice


def run_ingestion(path):
    '''Test the ingestion prompt on one file.'''
    logs.stage(f"TEST INGESTION - {os.path.basename(path)}")
    data = ingest_invoice(path)
    data = attach_prior_invoice(data)
    logs.ingestion(data)
    logs.data(data)
    logs.end("ingestion stage complete")
    return data


def run_validation(path):
    '''Test validation (runs ingestion first for realistic input).'''
    data = run_ingestion(path)
    logs.stage(f"TEST VALIDATION - {os.path.basename(path)}")
    data = validate_invoice(data)
    logs.validation(data)
    logs.data(data)
    logs.end("validation stage complete")
    return data


def run_approval(path):
    '''Test approval (runs ingestion + validation first).'''
    data = run_validation(path)
    logs.stage(f"TEST APPROVAL - {os.path.basename(path)}")
    data = approve_invoice(data)
    logs.approval(data)
    logs.data(data)
    logs.end("approval stage complete (draft + critique included above)")
    return data


def run_all(path):
    '''Run all three agents with clear per-stage output. No payment / DB writes.'''
    logs.stage(f"TEST ALL - {os.path.basename(path)}")
    logs.lines("Payment and invoice-history writes are skipped in prompt testing.")
    result = run_approval(path)
    logs.rollup(result)
    logs.end("full prompt test complete (no payment)")
    return result


parser = argparse.ArgumentParser(
    description="Test agent prompts one stage at a time or as a full chain."
)
parser.add_argument(
    "--stage",
    choices=["ingestion", "validation", "approval", "all"],
    required=True,
    help="Which stage to test.",
)
parser.add_argument(
    "--invoice_path",
    required=True,
    help="Path to one invoice file.",
)
args = parser.parse_args()

if not os.path.exists(args.invoice_path):
    raise SystemExit(f"Invoice path not found: {args.invoice_path}")

if args.stage == "ingestion":
    run_ingestion(args.invoice_path)
elif args.stage == "validation":
    run_validation(args.invoice_path)
elif args.stage == "approval":
    run_approval(args.invoice_path)
else:
    run_all(args.invoice_path)
