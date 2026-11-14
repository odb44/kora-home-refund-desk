"""
Kora Home: agent hooks.

Audits turns/tool calls and enforces refund quote, approval, and ticket-cap rules.
"""
import json
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import (
    AfterInvocationEvent,
    AfterToolCallEvent,
    BeforeInvocationEvent,
    BeforeToolCallEvent,
)

QUOTE_TOOL = "calculate_refund"
REFUND_TOOL = "issue_refund"
APPROVAL_THRESHOLD = Decimal("500.00")
TICKET_REFUND_CAP = Decimal("1000.00")
AGENT_IDENTITY = "agent:kora-support-ada"


def state_value(state: Any, key: str, default: Any = None) -> Any:
    """Read Strands JSONSerializableDict safely (its get accepts one key)."""
    value = state.get(key)
    return default if value is None else value


def normalize_order_id(value: Any) -> str:
    return str(value or "").strip().upper()


def as_decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def tool_name(event: Any) -> str:
    selected = getattr(event, "selected_tool", None)
    if selected is not None:
        spec = getattr(selected, "tool_spec", None) or {}
        if isinstance(spec, dict) and spec.get("name"):
            return str(spec["name"])
        name = getattr(selected, "name", None)
        if name:
            return str(name)

    tool_use = getattr(event, "tool_use", None) or {}
    if isinstance(tool_use, dict):
        return str(tool_use.get("name", "unknown"))
    return str(getattr(tool_use, "name", "unknown"))


def tool_input(event: Any) -> dict[str, Any]:
    tool_use = getattr(event, "tool_use", None) or {}
    if isinstance(tool_use, dict):
        value = tool_use.get("input", {})
    else:
        value = getattr(tool_use, "input", {})
    return value if isinstance(value, dict) else {}


def tool_use_id(event: Any) -> str:
    tool_use = getattr(event, "tool_use", None) or {}
    if isinstance(tool_use, dict):
        return str(tool_use.get("toolUseId", tool_use.get("tool_use_id", "")))
    return str(
        getattr(tool_use, "toolUseId", "")
        or getattr(tool_use, "tool_use_id", "")
    )


def result_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        content = result.get("content", [])
        pieces = [
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and item.get("text") is not None
        ]
        return "\n".join(pieces) if pieces else json.dumps(result, default=str)
    content = getattr(result, "content", None)
    if content:
        pieces = [
            str(getattr(item, "text", ""))
            for item in content
            if getattr(item, "text", None) is not None
        ]
        if pieces:
            return "\n".join(pieces)
    return str(result)


def get_agent_state(agent: Any):
    """Return Strands' JSONSerializableDict and initialize required keys."""
    state = agent.state
    defaults = {
        "quotes": {},
        "approvals": [],
        "refunds": [],
        "refund_total": 0.0,
    }
    for key, default in defaults.items():
        if state.get(key) is None:
            state.set(key, default)
    return state


def refund_entry_from_result(result: Any) -> dict[str, Any] | None:
    text = result_text(result)
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(parsed, dict):
        for key in ("refund", "entry", "refund_entry"):
            if isinstance(parsed.get(key), dict):
                return parsed[key]
        return parsed
    return None


class AuditLogHook(HookProvider):
    def __init__(self, ticket_id: str, log_dir: str = "logs"):
        self.ticket_id = ticket_id.upper()
        self.log_path = Path(log_dir) / f"audit_{self.ticket_id}.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._tool_starts: dict[str, float] = {}

    def _write(self, payload: dict[str, Any]) -> None:
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, default=str) + "\n")

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeInvocationEvent, self.on_turn_start)
        registry.add_callback(AfterInvocationEvent, self.on_turn_end)
        registry.add_callback(BeforeToolCallEvent, self.on_tool_start)
        registry.add_callback(AfterToolCallEvent, self.on_tool_end)

    def on_turn_start(self, event: BeforeInvocationEvent) -> None:
        self._write({
            "event": "turn_start",
            "ticket_id": self.ticket_id,
            "timestamp": time.time(),
        })

    def on_turn_end(self, event: AfterInvocationEvent) -> None:
        state = get_agent_state(event.agent)
        self._write({
            "event": "turn_end",
            "ticket_id": self.ticket_id,
            "timestamp": time.time(),
            "refund_total": state_value(state, "refund_total", 0.0),
        })

    def on_tool_start(self, event: BeforeToolCallEvent) -> None:
        call_id = tool_use_id(event) or f"{tool_name(event)}:{time.time_ns()}"
        self._tool_starts[call_id] = time.perf_counter()
        event.invocation_state.setdefault("kora_audit_call_id", call_id)

    def on_tool_end(self, event: AfterToolCallEvent) -> None:
        call_id = (
            tool_use_id(event)
            or event.invocation_state.get("kora_audit_call_id", "")
        )
        start = self._tool_starts.pop(call_id, None)
        duration_ms = (
            round((time.perf_counter() - start) * 1000, 2)
            if start is not None
            else round((getattr(event, "duration", 0.0) or 0.0) * 1000, 2)
        )
        result = getattr(event, "result", None)
        exception = getattr(event, "exception", None)
        cancel_message = getattr(event, "cancel_message", None)
        self._write({
            "event": "tool_call",
            "ticket_id": self.ticket_id,
            "tool": tool_name(event),
            "toolUseId": call_id,
            "input": tool_input(event),
            "status": "error" if exception or cancel_message else "success",
            "duration_ms": duration_ms,
            "output_preview": str(
                cancel_message or exception or result_text(result)
            )[:300],
        })


class FixedRefundArgsHook(HookProvider):
    def __init__(self, ticket_id: str):
        self.ticket_id = ticket_id.upper()

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.on_before_tool_call)

    def on_before_tool_call(self, event: BeforeToolCallEvent) -> None:
        if tool_name(event) != REFUND_TOOL:
            return
        tool_use = getattr(event, "tool_use", None)
        if isinstance(tool_use, dict):
            arguments = tool_use.setdefault("input", {})
        else:
            arguments = getattr(tool_use, "input", None)
        if isinstance(arguments, dict):
            arguments["ticket_id"] = self.ticket_id
            arguments["issued_by"] = AGENT_IDENTITY


class RefundGuardrailHook(HookProvider):
    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.on_before_tool_call)
        registry.add_callback(AfterToolCallEvent, self.on_after_tool_call)
        registry.add_callback(AfterToolCallEvent, self.on_refund_result)

    def on_before_tool_call(self, event: BeforeToolCallEvent) -> None:
        if tool_name(event) != REFUND_TOOL:
            return

        state = get_agent_state(event.agent)
        quotes = dict(state_value(state, "quotes", {}) or {})
        approvals = list(state_value(state, "approvals", []) or [])
        refund_total = state_value(state, "refund_total", 0.0)
        arguments = tool_input(event)

        order_id = normalize_order_id(arguments.get("order_id"))
        if not order_id:
            event.cancel_tool = (
                "BLOCKED BY POLICY: Missing order ID. Verify the order and "
                "calculate its refund before retrying."
            )
            return

        try:
            amount = as_decimal(arguments.get("amount"))
            if not amount.is_finite() or amount <= 0:
                raise InvalidOperation
            amount = amount.quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError, TypeError):
            event.cancel_tool = (
                "BLOCKED BY POLICY: Invalid refund amount. Call calculate_refund "
                "for this order and use its exact quoted amount."
            )
            return

        quote_key = next(
            (key for key in quotes if normalize_order_id(key) == order_id),
            None,
        )
        if quote_key is None:
            event.cancel_tool = (
                f"BLOCKED BY POLICY: No eligible refund quote is recorded for "
                f"{order_id}. Call calculate_refund and only retry if it returns "
                "eligible=true."
            )
            return

        try:
            quoted_amount = as_decimal(quotes[quote_key]).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError, TypeError):
            event.cancel_tool = (
                f"BLOCKED BY POLICY: The saved quote for {order_id} is invalid. "
                "Recalculate the refund before retrying."
            )
            return

        if amount != quoted_amount:
            event.cancel_tool = (
                f"BLOCKED BY POLICY: Requested amount ${amount:.2f} does not "
                f"match the exact quote ${quoted_amount:.2f} for {order_id}. "
                "Use the quoted amount; do not split or alter it."
            )
            return

        approval_key = next(
            (key for key in approvals if normalize_order_id(key) == order_id),
            None,
        )
        if amount > APPROVAL_THRESHOLD and approval_key is None:
            event.cancel_tool = (
                f"BLOCKED BY POLICY: {order_id} requires supervisor approval "
                f"because ${amount:.2f} exceeds $500.00. Ask for approval and, "
                "once you hear it was granted, call issue_refund again with the "
                "same order and exact quoted amount."
            )
            return

        try:
            current_total = as_decimal(refund_total)
        except (InvalidOperation, ValueError, TypeError):
            current_total = Decimal("0.00")

        if current_total + amount > TICKET_REFUND_CAP:
            event.cancel_tool = (
                f"BLOCKED BY POLICY: This refund would bring the ticket total to "
                f"${current_total + amount:.2f}, exceeding the $1,000.00 ticket "
                "limit. Do not issue a partial refund or change the quoted amount. "
                "Escalate to a supervisor."
            )
            return

        event.invocation_state["kora_pending_refund"] = {
            "order_id": order_id,
            "amount": str(amount),
            "quote_key": quote_key,
            "approval_key": approval_key,
        }

    def on_after_tool_call(self, event: AfterToolCallEvent) -> None:
        if tool_name(event) != QUOTE_TOOL:
            return
        if getattr(event, "exception", None) is not None:
            return

        try:
            quote_result = json.loads(result_text(getattr(event, "result", None)))
        except (json.JSONDecodeError, TypeError):
            return
        if not isinstance(quote_result, dict) or quote_result.get("eligible") is not True:
            return

        order_id = normalize_order_id(quote_result.get("order_id"))
        if not order_id:
            return
        try:
            amount = as_decimal(quote_result.get("refund_amount")).quantize(
                Decimal("0.01")
            )
            if not amount.is_finite() or amount <= 0:
                return
        except (InvalidOperation, ValueError, TypeError):
            return

        state = get_agent_state(event.agent)
        quotes = dict(state_value(state, "quotes", {}) or {})
        for existing in list(quotes):
            if normalize_order_id(existing) == order_id:
                del quotes[existing]
        quotes[order_id] = str(amount)
        state.set("quotes", quotes)

    def on_refund_result(self, event: AfterToolCallEvent) -> None:
        if tool_name(event) != REFUND_TOOL:
            return
        if getattr(event, "exception", None) is not None:
            return

        pending = event.invocation_state.get("kora_pending_refund")
        if not pending:
            return

        result = getattr(event, "result", None)
        try:
            parsed = json.loads(result_text(result))
        except (json.JSONDecodeError, TypeError):
            return
        if not isinstance(parsed, dict):
            return
        if parsed.get("success") is False or parsed.get("error"):
            return

        order_id = pending["order_id"]
        amount = as_decimal(pending["amount"])
        entry = refund_entry_from_result(result) or parsed

        state = get_agent_state(event.agent)
        refunds = list(state_value(state, "refunds", []) or [])
        refunds.append(entry)
        state.set("refunds", refunds)

        current_total = as_decimal(state_value(state, "refund_total", 0.0))
        state.set("refund_total", float(current_total + amount))

        approvals = list(state_value(state, "approvals", []) or [])
        approvals = [
            item for item in approvals
            if normalize_order_id(item) != order_id
        ]
        state.set("approvals", approvals)

        quotes = dict(state_value(state, "quotes", {}) or {})
        for existing in list(quotes):
            if normalize_order_id(existing) == order_id:
                del quotes[existing]
        state.set("quotes", quotes)

        event.invocation_state.pop("kora_pending_refund", None)
