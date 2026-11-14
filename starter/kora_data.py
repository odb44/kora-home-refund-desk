"""
Kora Home: data access helpers (PROVIDED, you do not need to change this file)

Every module in this classwork reads the JSON "database" in ../data through these helpers,
so the MCP server and your native Python tools always see the same records.
"""
import json
import os
from datetime import date, datetime
from pathlib import Path


def _find_data_dir() -> Path:
    """Use KORA_DATA_DIR if set, otherwise walk up from this file until a data/ folder is found."""
    if os.getenv("KORA_DATA_DIR"):
        return Path(os.environ["KORA_DATA_DIR"]).resolve()
    for parent in Path(__file__).resolve().parents:
        if (parent / "data" / "orders.json").exists():
            return parent / "data"
    raise FileNotFoundError("Could not find the classwork data/ folder. Set KORA_DATA_DIR.")


DATA_DIR = _find_data_dir()
LEDGER_FILE = DATA_DIR / "refund_ledger.json"

# "Today" for every policy calculation, fixed so everyone gets the same answers
REFERENCE_DATE = date(2026, 10, 16)


def _load(name: str):
    return json.loads((DATA_DIR / name).read_text())


def load_customers() -> list[dict]:
    return _load("customers.json")


def load_products() -> list[dict]:
    return _load("products.json")


def load_orders() -> list[dict]:
    return _load("orders.json")


def load_ledger() -> list[dict]:
    if not LEDGER_FILE.exists():
        # First run: start from the seed ledger (python reset_lab.py restores it later)
        LEDGER_FILE.write_text((DATA_DIR / "refund_ledger.seed.json").read_text())
    return json.loads(LEDGER_FILE.read_text())


def append_to_ledger(entry: dict) -> None:
    ledger = load_ledger()
    ledger.append(entry)
    LEDGER_FILE.write_text(json.dumps(ledger, indent=2))


def find_customer_by_email(email: str) -> dict | None:
    email = email.strip().lower()
    return next((c for c in load_customers() if c["email"].lower() == email), None)


def get_customer(customer_id: str) -> dict | None:
    return next((c for c in load_customers() if c["customer_id"] == customer_id), None)


def get_product(sku: str) -> dict | None:
    return next((p for p in load_products() if p["sku"] == sku), None)


def get_order(order_id: str) -> dict | None:
    """Return the order with its *effective* status (``refunded`` if it is in the ledger)."""
    order_id = order_id.strip().upper()
    order = next((o for o in load_orders() if o["order_id"] == order_id), None)
    if order is None:
        return None
    order = dict(order)
    if any(r["order_id"] == order_id for r in load_ledger()):
        order["status"] = "refunded"
    return order


def days_since(iso_date: str) -> int:
    """Whole days between an ISO date (YYYY-MM-DD) and REFERENCE_DATE."""
    return (REFERENCE_DATE - date.fromisoformat(iso_date)).days


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
