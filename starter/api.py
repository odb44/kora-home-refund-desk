"""Local HTTP adapter for the Kora Home refund desk.

The console application remains supported. This adapter exposes the same Ada
agent, session state, MCP tools and guardrails to the React operations UI.
Run from the project root with: uv run uvicorn starter.api:app --reload
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)
import asyncio
import json
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from starter.support_desk import (
    SESSION_DIR,
    TICKET_DIR,
    build_agent,
    build_mcp_client,
    close_ticket,
    state_value,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
AUDIT_DIR = HERE / "logs"
TICKET_PATTERN = re.compile(r"^TCK-\d{4,}$")


class CreateTicketRequest(BaseModel):
    subject: str = Field(min_length=3, max_length=160)
    initial_message: str | None = Field(default=None, max_length=4000)


class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ApprovalRequest(BaseModel):
    order_id: str = Field(pattern=r"(?i)^ORD-\d+$")


def _ticket_file(ticket_id: str) -> Path:
    return TICKET_DIR / f"{ticket_id}.meta.json"


def _read_ticket(ticket_id: str) -> dict[str, Any]:
    path = _ticket_file(ticket_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_ticket(ticket: dict[str, Any]) -> None:
    TICKET_DIR.mkdir(parents=True, exist_ok=True)
    _ticket_file(ticket["ticket_id"]).write_text(
        json.dumps(ticket, indent=2), encoding="utf-8"
    )


def _safe_ticket_id(ticket_id: str) -> str:
    value = ticket_id.strip().upper()
    if not TICKET_PATTERN.fullmatch(value):
        raise HTTPException(status_code=400, detail="Invalid ticket ID.")
    return value


def _audit_events(ticket_id: str) -> list[dict[str, Any]]:
    path = AUDIT_DIR / f"audit_{ticket_id}.jsonl"
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events[-100:][::-1]


def _ticket_summary(ticket: dict[str, Any]) -> dict[str, Any]:
    ticket_id = ticket["ticket_id"]
    report_path = TICKET_DIR / f"{ticket_id}.json"
    report: dict[str, Any] = {}
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report = {}
    refunds = report.get("refunds", [])
    return {
        **ticket,
        "customer_id": report.get("customer_id"),
        "orders_discussed": report.get("orders_discussed", []),
        "resolution": report.get("resolution"),
        "total_refunded": report.get("total_refunded", 0),
        "refunds": refunds,
    }


@asynccontextmanager
async def lifespan(application: FastAPI):
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    TICKET_DIR.mkdir(parents=True, exist_ok=True)
    client = build_mcp_client()
    client.__enter__()
    try:
        application.state.mcp_client = client
        application.state.mcp_tools = client.list_tools_sync()
        application.state.agents = {}
        application.state.agent_locks = {}
        yield
    finally:
        client.__exit__(None, None, None)


app = FastAPI(
    title="Kora Home Refund Desk API",
    version="1.0.0",
    description="Local API adapter for Ada. Refund policy and guardrails remain in the existing agent.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _get_agent(ticket_id: str):
    agents = app.state.agents
    if ticket_id not in agents:
        # FileSessionManager restores both conversation and agent state.
        agents[ticket_id] = build_agent(ticket_id, app.state.mcp_tools)
        app.state.agent_locks[ticket_id] = asyncio.Lock()
    return agents[ticket_id]


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "kora-refund-desk"}


@app.get("/api/tickets")
async def list_tickets():
    TICKET_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for path in sorted(TICKET_DIR.glob("TCK-*.meta.json"), reverse=True):
        try:
            ticket = json.loads(path.read_text(encoding="utf-8"))
            items.append(_ticket_summary(ticket))
        except (json.JSONDecodeError, KeyError):
            continue
    return {"items": items, "total": len(items)}


@app.post("/api/tickets", status_code=status.HTTP_201_CREATED)
async def create_ticket(payload: CreateTicketRequest):
    TICKET_DIR.mkdir(parents=True, exist_ok=True)
    existing = [
        int(match.group(1))
        for path in TICKET_DIR.glob("TCK-*.meta.json")
        if (match := re.match(r"TCK-(\d+)\.meta\.json$", path.name))
    ]
    ticket_id = f"TCK-{max(existing, default=1048) + 1:04d}"
    ticket = {
        "ticket_id": ticket_id,
        "subject": payload.subject.strip(),
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_ticket(ticket)
    _get_agent(ticket_id)
    if payload.initial_message and payload.initial_message.strip():
        await _send_message(ticket_id, payload.initial_message.strip())
    return _ticket_summary(_read_ticket(ticket_id))


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: str):
    ticket_id = _safe_ticket_id(ticket_id)
    ticket = _read_ticket(ticket_id)
    return {**_ticket_summary(ticket), "activity": _audit_events(ticket_id)}


async def _send_message(ticket_id: str, message: str) -> dict[str, Any]:
    agent = _get_agent(ticket_id)
    lock = app.state.agent_locks[ticket_id]
    chunks: list[str] = []
    async with lock:
        async for event in agent.stream_async(message):
            if isinstance(event, dict) and event.get("data"):
                chunks.append(str(event["data"]))
    ticket = _read_ticket(ticket_id)
    ticket["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_ticket(ticket)
    return {"ticket_id": ticket_id, "reply": "".join(chunks).strip(), "activity": _audit_events(ticket_id)}


@app.post("/api/tickets/{ticket_id}/messages")
async def send_message(ticket_id: str, payload: MessageRequest):
    ticket_id = _safe_ticket_id(ticket_id)
    _read_ticket(ticket_id)
    try:
        return await _send_message(ticket_id, payload.message.strip())
    except Exception as exc:
        logger.exception(
            "Ada failed to process message for ticket %s",
            ticket_id,
        )
        # Keep internal details out of the API response.
        raise HTTPException(
            status_code=502,
            detail=f"Ada could not complete this turn: {type(exc).__name__}.",
        ) from exc


@app.post("/api/tickets/{ticket_id}/approve")
async def approve_refund(
    ticket_id: str,
    payload: ApprovalRequest,
    x_supervisor_token: str | None = Header(default=None),
):
    configured_token = os.getenv("KORA_SUPERVISOR_TOKEN", "")
    if not configured_token:
        raise HTTPException(status_code=503, detail="Supervisor approval is not configured.")
    if not x_supervisor_token or not secrets.compare_digest(x_supervisor_token, configured_token):
        raise HTTPException(status_code=403, detail="Supervisor authentication failed.")
    ticket_id = _safe_ticket_id(ticket_id)
    _read_ticket(ticket_id)
    agent = _get_agent(ticket_id)
    order_id = payload.order_id.strip().upper()
    async with app.state.agent_locks[ticket_id]:
        approvals = list(state_value(agent.state, "approvals", []) or [])
        if order_id not in approvals:
            approvals.append(order_id)
            agent.state.set("approvals", approvals)
    return {"ticket_id": ticket_id, "order_id": order_id, "approval_recorded": True}


@app.post("/api/tickets/{ticket_id}/escalate")
async def escalate_ticket(ticket_id: str):
    ticket_id = _safe_ticket_id(ticket_id)
    ticket = _read_ticket(ticket_id)
    if ticket.get("status") == "closed":
        raise HTTPException(status_code=409, detail="A closed ticket cannot be escalated.")
    ticket["status"] = "escalated"
    ticket["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_ticket(ticket)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    with (AUDIT_DIR / f"audit_{ticket_id}.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({
            "timestamp": ticket["updated_at"],
            "event": "operator_escalation",
            "status": "recorded",
            "output_preview": "Ticket escalated for human supervisor review.",
        }) + "\n")
    return {"ticket_id": ticket_id, "status": "escalated"}


@app.get("/api/tickets/{ticket_id}/activity")
async def ticket_activity(ticket_id: str):
    ticket_id = _safe_ticket_id(ticket_id)
    _read_ticket(ticket_id)
    return {"items": _audit_events(ticket_id)}


@app.post("/api/tickets/{ticket_id}/close")
async def close(ticket_id: str):
    ticket_id = _safe_ticket_id(ticket_id)
    ticket = _read_ticket(ticket_id)
    agent = _get_agent(ticket_id)
    try:
        async with app.state.agent_locks[ticket_id]:
            summary = close_ticket(agent, ticket_id)
        ticket["status"] = "closed"
        ticket["updated_at"] = datetime.now(timezone.utc).isoformat()
        _write_ticket(ticket)
        return {"ticket": _ticket_summary(ticket), "summary": summary.model_dump()}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ticket could not be closed: {type(exc).__name__}.") from exc


def _message_text(message: Any) -> str:
    if not isinstance(message, dict):
        return ""
    parts = message.get("content", [])
    if isinstance(parts, str):
        return parts
    if not isinstance(parts, list):
        return ""
    text_parts = []
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            text_parts.append(part["text"])
    return "\n".join(text_parts).strip()


@app.get("/api/tickets/{ticket_id}/messages")
async def ticket_messages(ticket_id: str):
    ticket_id = _safe_ticket_id(ticket_id)
    _read_ticket(ticket_id)
    agent = _get_agent(ticket_id)
    messages = []
    for message in getattr(agent, "messages", []) or []:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = _message_text(message)
        if content:
            messages.append({"role": "customer" if role == "user" else "ada", "content": content})
    return {"items": messages}
