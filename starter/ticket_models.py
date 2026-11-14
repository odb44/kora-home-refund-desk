"""
Kora Home: structured ticket summary  (TASK 6)

Define a Pydantic model TicketSummary that the CRM can ingest when a ticket is closed.
Every field needs a Field(description=...), because the model reads those descriptions.

Required fields:
    ticket_id            str
    customer_id          optional str (None if the customer was never verified)
    orders_discussed     list of order IDs
    issue_category       one of: change_of_mind, defective, damaged_in_transit, order_status, other
    resolution           one of: refund_issued, refund_denied, escalated_to_supervisor, information_only, unresolved
    total_refunded       float, >= 0
    customer_sentiment   one of: positive, neutral, negative
    follow_up_required   bool
    summary              str (at most 3 sentences)

Hint: Course 2 Lab 2, bedrock_model.py (BookAnalysis). Use typing.Literal for the fixed choices.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field

class TicketSummary(BaseModel):

    """Validated summary of a completed or unresolved support ticket."""

    # The ticket being summarized, e.g. TCK-1001.
    ticket_id: str = Field(
        description="Unique ticket identifier, such as TCK-1001."
    )

    # Remains None if the customer was never successfully verified.
    customer_id: Optional[str] = Field(
        default=None,
        description="Verified customer ID, or None if the customer was not verified."
    )

    # Order IDs discussed during the conversation.
    orders_discussed: list[str] = Field(
        description="List of order IDs discussed during this ticket."
    )

    # Literal restricts this field to the specified categories.
    issue_category: Literal[
        "change_of_mind",
        "defective",
        "damaged_in_transit",
        "order_status",
        "other",
    ] = Field(
        description="Main category of the customer's issue."
    )

    # Only these five resolution values are accepted.
    resolution: Literal[
        "refund_issued",
        "refund_denied",
        "escalated_to_supervisor",
        "information_only",
        "unresolved",
    ] = Field(
        description="Final outcome of the support ticket."
    )

    # The application will overwrite this with its trusted state value.
    total_refunded: float = Field(
        ge=0,
        description="Total amount successfully refunded for this ticket, in USD."
    )

    # A controlled classification of the customer's overall sentiment.
    customer_sentiment: Literal[
        "positive",
        "neutral",
        "negative",
    ] = Field(
        description="Overall customer sentiment at the end of the interaction."
    )

    # Indicates whether another action is still needed.
    follow_up_required: bool = Field(
        description="Whether further support or supervisor action is required."
    )

    # Keep the summary concise for the CRM.
    summary: str = Field(
        max_length=1000,
        description="Concise ticket summary in no more than three sentences."
    )
