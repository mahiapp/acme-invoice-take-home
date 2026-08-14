# SQLite helpers used by the validation agent tools and invoice history tracking.

import os
import sqlite3
from datetime import datetime, timezone

from utils import is_approved

DB = os.path.join(os.path.dirname(__file__), "inventory.db")


def _connect():
    '''Open a connection to the inventory database.'''
    if not os.path.exists(DB):
        raise FileNotFoundError(
            f"Inventory DB not found at {DB}. Run: python data/db_setup.py"
        )
    return sqlite3.connect(DB)


def _normalize_item_name(name):
    '''Normalize item names for fuzzy matching (e.g. "Widget A" -> "widgeta").'''
    if not name:
        return ""
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def get_item(name):
    '''Return (catalog_name, stock, expected_unit_price), or None if missing.

    Tries an exact match first, then a fuzzy match that ignores spaces and case
    so names like "Widget A" still resolve to "WidgetA".
    '''
    conn = _connect()
    row = conn.execute(
        "SELECT item, stock, expected_unit_price FROM inventory WHERE item = ?",
        (name,),
    ).fetchone()
    if row:
        conn.close()
        return row

    target = _normalize_item_name(name)
    rows = conn.execute(
        "SELECT item, stock, expected_unit_price FROM inventory"
    ).fetchall()
    conn.close()
    for catalog_name, stock, price in rows:
        if _normalize_item_name(catalog_name) == target:
            return (catalog_name, stock, price)
    return None


def get_invoice(invoice_number):
    '''Return a previously processed invoice as a dict, or None.'''
    if not invoice_number:
        return None
    conn = _connect()
    row = conn.execute(
        """
        SELECT invoice_number, vendor, total_amount, decision, path,
               processed_at, is_revised
        FROM invoices
        WHERE invoice_number = ?
        """,
        (invoice_number,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "invoice_number": row[0],
        "vendor": row[1],
        "total_amount": row[2],
        "decision": row[3],
        "path": row[4],
        "processed_at": row[5],
        "is_revised": bool(row[6]),
    }


def save_invoice(invoice_number, vendor, total_amount, decision, path, is_revised=False):
    '''Insert or replace a processed invoice record.'''
    conn = _connect()
    conn.execute(
        """
        INSERT OR REPLACE INTO invoices
        (invoice_number, vendor, total_amount, decision, path, processed_at, is_revised)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            invoice_number,
            vendor,
            total_amount,
            decision,
            path,
            datetime.now(timezone.utc).isoformat(),
            1 if is_revised else 0,
        ),
    )
    conn.commit()
    conn.close()


def attach_prior_invoice(data):
    '''Flag invoices that were already processed and attach prior record details.'''
    prior = get_invoice(data.get("invoice_number"))
    if prior is None:
        data["previously_processed"] = False
        data["prior_invoice"] = None
        return data

    data["previously_processed"] = True
    data["prior_invoice"] = prior
    issues = list(data.get("issues") or [])
    issues.append(
        f"Invoice {data.get('invoice_number')} was previously processed on "
        f"{prior['processed_at']} (decision={prior['decision']}, "
        f"total={prior['total_amount']}, path={prior['path']})."
    )
    data["issues"] = issues
    return data


def record_invoice(result, path):
    '''Persist invoice history after a completed run.'''
    invoice_number = result.get("invoice_number")
    if not invoice_number:
        return

    approved = is_approved(result.get("decision"))
    prior_existed = bool(result.get("previously_processed"))

    # Approved invoices replace any prior record (mark revised when replacing).
    # First-time rejects are stored too. Rejected duplicates leave the old record.
    if approved:
        save_invoice(
            invoice_number,
            result.get("vendor"),
            result.get("total_amount"),
            result.get("decision"),
            path,
            is_revised=prior_existed,
        )
    elif not prior_existed:
        save_invoice(
            invoice_number,
            result.get("vendor"),
            result.get("total_amount"),
            result.get("decision"),
            path,
            is_revised=False,
        )
