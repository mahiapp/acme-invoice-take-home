# Acme Invoice Multi-Agent System

Local prototype that automates invoice processing for Acme Corp: extract data -> check inventory -> approve/reject -> mock payment. Built with Grok and LangGraph.

## Setup

```bash
pip3 install -r requirements.txt
cp .env.example .env
# put YOUR xAI API key in .env (do not commit .env)
# XAI_API_KEY=...
python3 data/db_setup.py
```

You need your own key from [console.x.ai](https://console.x.ai). The repo does not ship a shared key.

## Run

One invoice:

```bash
python3 main.py --invoice_path=invoices/invoice_1001.txt
```

Whole folder:

```bash
python3 main.py --invoice_path=invoices
```

### Prompt testing

Useful while editing prompts. Does not pay or save invoice history:

```bash
python3 test_prompts.py --stage all --invoice_path=invoices/invoice_1001.txt
python3 test_prompts.py --stage ingestion --invoice_path=invoices/invoice_1002.txt
python3 test_prompts.py --stage validation --invoice_path=invoices/invoice_1009.json
python3 test_prompts.py --stage approval --invoice_path=invoices/invoice_1003.txt
```

### Suggested test invoices

| File | What it covers |
|------|----------------|
| `invoice_1001.txt` | Clean happy path |
| `invoice_1002.txt` | Typos + overstock |
| `invoice_1003.txt` | Fake/zero-stock item + urgent payment language |
| `invoice_1008.txt` | Unknown items |
| `invoice_1009.json` | Negative quantity |
| `invoice_1010.txt` | Rush-order price difference |
| `invoice_1011.pdf` | PDF input |
| `invoice_1004.json` -> `invoice_1004_revised.json` | Duplicate / revision |

## How it works

1. **Ingestion** - Grok pulls fields out of messy invoice files (PDFs with pdfplumber; other files as text)
2. **Validation** - Python checks SQLite inventory and math, then Grok decides pass/fail/review
3. **Approval** - draft decision, critique, then final approve/reject
4. **Payment** - normal `mock_payment()` function if approved (not an agent)

LangGraph runs the three agents in order. Inventory and processed invoices are stored in `data/inventory.db`.

## Design decisions

- **Batch mode** - the assignment wants a single `--invoice_path`; a folder path runs everything inside it
- **One ingestion flow** - same agent handles PDF and text-like files instead of separate parsers
- **Invoices table** - remembers processed invoice numbers so duplicates/revisions get flagged; if approval accepts a revision, it replaces the old record
- **Expected prices in inventory** - price mismatches are warnings, not automatic rejects (rush fees can be real)
- **Payment is a function** - keeps payment simple and predictable
- **Inventory does not change** - stock is not reduced after each invoice in this MVP
- **Tax and shipping** - total is checked as line items + tax + shipping, not line items alone

## Next steps

- Stop early on clear rejects (e.g. unknown items) so later agents do not burn tokens
- Partial payments when some line items check out and others do not
- Update stock after an invoice is approved
- A simple UI instead of terminal-only output
- Batch a chosen list of files, not only one file or the whole folder
- Better DB setup (re-running seed without errors)
- For revisions, pay only the difference from the earlier invoice
