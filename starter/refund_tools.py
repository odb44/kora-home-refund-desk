"""
Kora Home: native Python tools  (TASK 3)

Implement calculate_refund as a Strands @tool that applies data/refund_policy.md exactly.

Signature (do not change the name or parameters):
    calculate_refund(order_id: str, reason: str) -> str

It must return a JSON *string* with these keys:
    {
      "order_id": "ORD-5001",
      "eligible": true,
      "refund_amount": 76.49,          # 0.0 when not eligible
      "rule_applied": "change_of_mind_restocking",
      "explanation": "15% restocking fee applied"
    }

Requirements:
    - Load the order, product and customer yourself with kora_data. Never accept a price,
      date or tier from the model as a parameter. (Why? Answer in REFLECTION.md.)
    - reason is one of: change_of_mind, defective, damaged_in_transit
    - Use decimal.Decimal with ROUND_HALF_UP for money.
    - Handle: unknown order, in_transit, already refunded, final_sale, out of window/warranty.
    - Check every boundary in the policy (≤ vs <) and the rule order. Your tool is tested against
      a different dataset than the one you see, so don't hard-code anything.

Hint: Course 1 Lab 4 (custom @tool). The docstring and type hints become the tool spec.
"""
import json
from decimal import Decimal, ROUND_HALF_UP

from strands import tool

try:
    from . import kora_data
except ImportError:  # pragma: no cover - direct console/script execution
    import kora_data



@tool
def calculate_refund(order_id: str, reason: str) -> str:
    """
    Calculate refund eligibility and amount using the official refund policy.

    reason must be change_of_mind, defective, or damaged_in_transit.
    All order, price, product, customer and date information comes from trusted data.
    Returns a JSON string.
    """
    order_id = str(order_id or "").strip().upper()

    result = {
        "order_id": order_id,
        "eligible": False,
        "refund_amount": 0.0,
        "rule_applied": "not_eligible",
        "explanation": "",
    }

    allowed_reasons = {
        "change_of_mind",
        "defective",
        "damaged_in_transit",
    }

    if reason not in allowed_reasons:
        result["explanation"] = (
            "Invalid reason. Use change_of_mind, defective, "
            "or damaged_in_transit."
        )
        return json.dumps(result)

    order = kora_data.get_order(order_id)
    if not order:
        result["explanation"] = "Order not found."
        return json.dumps(result)

    if (
        str(order.get("status", "")).lower() != "delivered"
        or not order.get("delivered_date")
    ):
        result["rule_applied"] = "not_delivered"
        result["explanation"] = (
            "The order has not been delivered. No refund can be calculated yet."
        )
        return json.dumps(result)

    ledger = kora_data.load_ledger()
    already_refunded = any(
        str(entry.get("order_id", "")).strip().upper() == order_id
        for entry in ledger
    )

    if already_refunded or str(order.get("status", "")).lower() == "refunded":
        result["rule_applied"] = "already_refunded"
        result["explanation"] = "This order has already been refunded."
        return json.dumps(result)

    product = kora_data.get_product(order.get("sku"))
    customer = kora_data.get_customer(order.get("customer_id"))

    if not product:
        result["explanation"] = "Product record not found for this order."
        return json.dumps(result)

    if not customer:
        result["explanation"] = "Customer record not found for this order."
        return json.dumps(result)

    days = kora_data.days_since(order["delivered_date"])
    price = Decimal(str(order["price_paid"]))

    amount = Decimal("0.00")
    rule = "not_eligible"
    explanation = "The order does not meet the refund policy requirements."

    if reason == "change_of_mind":
        # Final-sale exclusion takes precedence over the Gold waiver.
        if product.get("final_sale"):
            rule = "final_sale"
            explanation = (
                "Final-sale products are not eligible for change-of-mind refunds."
            )
        elif days <= 30:
            if str(customer.get("tier", "")).strip().lower() == "gold":
                amount = price
                rule = "gold_change_of_mind"
                explanation = "Gold-tier benefit waives the 15% restocking fee."
            else:
                amount = price * Decimal("0.85")
                rule = "change_of_mind_restocking"
                explanation = "15% restocking fee applied."
        else:
            rule = "outside_change_of_mind_window"
            explanation = "Change-of-mind refunds are available within 30 days."

    elif reason == "defective":
        if days <= 30:
            amount = price
            rule = "defective_full_refund"
            explanation = "Full refund for a defect reported within 30 days."
        else:
            warranty_days = int(product.get("warranty_months", 0)) * 30
            if warranty_days > 0 and days <= warranty_days:
                amount = (
                    price
                    * Decimal(warranty_days - days)
                    / Decimal(warranty_days)
                )
                rule = "defective_prorated_warranty"
                explanation = (
                    "Prorated defective-item refund based on remaining warranty."
                )
            else:
                rule = "outside_warranty"
                explanation = "The warranty has expired. Offer paid repair."

    elif reason == "damaged_in_transit":
        if days <= 7:
            amount = price
            rule = "damaged_in_transit_full_refund"
            explanation = "Full refund for transit damage reported within 7 days."
        else:
            rule = "transit_claim_late"
            explanation = (
                "The transit-damage window has passed. The issue may be "
                "reassessed as defective."
            )

    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if amount > Decimal("0.00"):
        result["eligible"] = True
        result["refund_amount"] = float(amount)

    result["rule_applied"] = rule
    result["explanation"] = explanation
    return json.dumps(result)
