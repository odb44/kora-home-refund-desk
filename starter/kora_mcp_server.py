"""MCP server for Kora Home's local order and refund system."""
from decimal import Decimal, InvalidOperation

from mcp.server.fastmcp import FastMCP

import kora_data

mcp = FastMCP("kora-order-system", log_level="WARNING")


def _clean_id(value: str) -> str:
    return str(value or "").strip().upper()


@mcp.tool()
def find_customer(email: str) -> dict:
    """Find a Kora Home customer by email address to verify their identity."""
    if not isinstance(email, str) or not email.strip():
        raise ValueError("A customer email address is required.")
    customer = kora_data.find_customer_by_email(email)
    if customer is None:
        raise ValueError("No customer was found for that email address.")
    # Return only the customer's record; do not disclose other customers.
    return customer


@mcp.tool()
def list_customer_orders(customer_id: str) -> list[dict]:
    """List orders belonging to a verified customer, including product names and effective statuses."""
    customer_id = str(customer_id or "").strip().upper()
    customer = kora_data.get_customer(customer_id)
    if customer is None:
        raise ValueError("Customer not found. Verify the customer's email first.")

    results = []
    for raw_order in kora_data.load_orders():
        if str(raw_order.get("customer_id", "")).strip().upper() != customer_id:
            continue
        order = kora_data.get_order(raw_order["order_id"])
        product = kora_data.get_product(order["sku"]) if order else None
        results.append({
            "order_id": order["order_id"],
            "customer_id": order["customer_id"],
            "product_name": product["name"] if product else "Unknown product",
            "price_paid": order["price_paid"],
            "order_date": order["order_date"],
            "delivered_date": order.get("delivered_date"),
            "status": order["status"],
        })
    return results


@mcp.tool()
def get_order_details(order_id: str) -> dict:
    """Get order details and product policy fields, including warranty, final-sale status, and delivery age."""
    order_id = _clean_id(order_id)
    if not order_id:
        raise ValueError("An order ID is required.")
    order = kora_data.get_order(order_id)
    if order is None:
        raise ValueError(f"Order {order_id} was not found.")
    product = kora_data.get_product(order["sku"])
    if product is None:
        raise ValueError(f"Product details for order {order_id} could not be found.")

    details = dict(order)
    details.update({
        "product_name": product["name"],
        "category": product.get("category"),
        "warranty_months": product["warranty_months"],
        "final_sale": bool(product.get("final_sale", False)),
        "days_since_delivery": (
            kora_data.days_since(order["delivered_date"])
            if order.get("delivered_date") else None
        ),
    })
    return details


@mcp.tool()
def issue_refund(
    order_id: str,
    amount: float,
    reason: str,
    ticket_id: str = "",
    issued_by: str = "",
) -> dict:
    """Issue a refund to the ledger after validating the order, delivery status, amount, and duplicate-refund status."""
    order_id = _clean_id(order_id)
    reason = str(reason or "").strip()
    if not order_id:
        raise ValueError("An order ID is required.")
    if not reason:
        raise ValueError("A refund reason is required.")

    order = kora_data.get_order(order_id)
    if order is None:
        raise ValueError(f"Order {order_id} was not found.")
    if order.get("status") == "refunded":
        raise ValueError(f"Order {order_id} has already been refunded.")
    if order.get("status") != "delivered" or not order.get("delivered_date"):
        raise ValueError("A refund can only be issued for an order that has been delivered.")

    try:
        refund_amount = Decimal(str(amount))
        price_paid = Decimal(str(order["price_paid"]))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Refund amount must be a valid number.") from None
    if not refund_amount.is_finite() or refund_amount <= Decimal("0"):
        raise ValueError("Refund amount must be greater than zero.")
    if refund_amount > price_paid:
        raise ValueError("Refund amount cannot exceed the price paid for the order.")
    refund_amount = refund_amount.quantize(Decimal("0.01"))

    ledger = kora_data.load_ledger()
    if any(_clean_id(item.get("order_id")) == order_id for item in ledger):
        raise ValueError(f"Order {order_id} already has a refund ledger entry.")

    max_number = 0
    for item in ledger:
        refund_id = str(item.get("refund_id", ""))
        if refund_id.startswith("RF-"):
            try:
                max_number = max(max_number, int(refund_id[3:]))
            except ValueError:
                pass

    entry = {
        "refund_id": f"RF-{max_number + 1:04d}",
        "order_id": order_id,
        "amount": float(refund_amount),
        "reason": reason,
        "ticket_id": str(ticket_id or "").strip(),
        "issued_by": str(issued_by or "").strip(),
        "issued_at": kora_data.now_iso(),
    }
    kora_data.append_to_ledger(entry)
    return {"success": True, **entry}


if __name__ == "__main__":
    # MCP stdio protocol uses stdout; do not print diagnostics here.
    mcp.run(transport="stdio")
