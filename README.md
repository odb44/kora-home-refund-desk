# Kora Home Refund Desk — Ada

**An AI-powered customer refund support desk with a human-supervised operations dashboard.**

Kora Home Refund Desk is a portfolio project demonstrating how an AI support agent can assist with customer refund enquiries while operating within deterministic business rules and approval controls.

Ada uses Amazon Bedrock through Strands, retrieves customer and order information through a local MCP server, calculates refunds using deterministic Python policy logic, and applies refund controls through hooks.

The project includes two interfaces:

1. **Console:** The original classwork workflow (`starter/support_desk.py`).
2. **Operations Dashboard:** A React/Vite interface connected to the agent through a FastAPI adapter (`starter/api.py`).

The API acts as an adapter around the existing agent. It does not introduce a separate refund calculator or bypass the agent's guardrails.

## Project Architecture

```text
.
├── data/
│   ├── customers.json
│   ├── orders.json
│   ├── products.json
│   ├── refund_policy.md
│   └── refund_ledger.seed.json
├── frontend/
│   ├── src/
│   └── package.json
├── starter/
│   ├── api.py
│   ├── guardrails.py
│   ├── kora_data.py
│   ├── kora_mcp_server.py
│   ├── refund_tools.py
│   ├── support_desk.py
│   └── ticket_models.py
├── .env.example
├── pyproject.toml
└── README.md
```

Runtime data is generated locally and excluded from version control:

- `starter/sessions/`
- `starter/logs/`
- `starter/tickets/`
- `data/refund_ledger.json`

## Technology Stack

| Component | Technology |
|---|---|
| AI Agent | Strands Agents |
| Language Model | Amazon Bedrock |
| Backend | Python, FastAPI |
| Tool Integration | Model Context Protocol (MCP) |
| Refund Calculation | Deterministic Python policy logic |
| Frontend | React 19, Vite |
| Persistence | Local JSON data and agent sessions |

## Requirements

- Python 3.12+
- Node.js 20.19+ or 22.12+
- `uv` package manager
- AWS credentials with access to the configured Amazon Bedrock model
- Bedrock model access enabled in the configured AWS region

## Backend Setup

From the project root:

```bash
uv sync
```

Copy `.env.example` to `starter/.env` and configure the required AWS settings:

```dotenv
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

Use an AWS profile or the standard AWS credential chain for authentication.

Do not commit `starter/.env`, AWS credentials, or other secrets.

For supervisor approval through the HTTP API, configure a long random token:

```dotenv
KORA_SUPERVISOR_TOKEN=your_long_random_token
```

The token is required by the API approval endpoint. Never expose it through a frontend environment variable.

### Run the Console

```bash
uv run python starter/support_desk.py --ticket TCK-1042
```

Available console commands:

| Command | Purpose |
|---|---|
| `/approve ORD-5004` | Record supervisor approval in the ticket's persistent agent state |
| `/state` | Inspect the guardrail state for the ticket |
| `/close` | Generate and save the structured ticket summary |
| `/quit` | Leave the ticket open for later resumption |

### Run the HTTP API

In a terminal from the project root:

```bash
uv run uvicorn starter.api:app --host 127.0.0.1 --port 8000 --reload
```

Health check:

`http://127.0.0.1:8000/api/health`

The API starts the local MCP server and reuses the same agent builder, persistent session manager, refund calculator, and hooks as the console.

### Run the Frontend

Open a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open the local Vite URL, normally:

`http://localhost:5173`

See [`frontend/README.md`](frontend/README.md) for frontend-specific setup and configuration.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | API health check |
| GET | `/api/tickets` | List locally persisted tickets |
| POST | `/api/tickets` | Create a ticket |
| GET | `/api/tickets/{ticket_id}` | Read ticket metadata and recent audit events |
| GET | `/api/tickets/{ticket_id}/messages` | Read persisted conversation messages |
| POST | `/api/tickets/{ticket_id}/messages` | Send a message to Ada |
| POST | `/api/tickets/{ticket_id}/approve` | Record supervisor approval |
| POST | `/api/tickets/{ticket_id}/escalate` | Record an operator escalation |
| GET | `/api/tickets/{ticket_id}/activity` | Read ticket audit events |
| POST | `/api/tickets/{ticket_id}/close` | Generate the structured ticket-close report |

Supervisor approval requires the `X-Supervisor-Token` header.

### Example: Create a Ticket

```bash
curl -X POST http://127.0.0.1:8000/api/tickets \
  -H "Content-Type: application/json" \
  -d '{"subject":"Refund request for a damaged item"}'
```

### Example: Supervisor Approval

```bash
curl -X POST http://127.0.0.1:8000/api/tickets/TCK-1042/approve \
  -H "Content-Type: application/json" \
  -H "X-Supervisor-Token: YOUR_CONFIGURED_TOKEN" \
  -d '{"order_id":"ORD-5004"}'
```

## Refund Safety Controls

The application demonstrates several controls designed to keep refund decisions within defined business rules:

- Customer verification is required before customer-specific order information is discussed.
- The refund calculator retrieves trusted order and policy data itself.
- The model does not independently determine refund amounts.
- Hooks enforce exact quoted amounts, supervisor approval above $500, and a $1,000 per-ticket ceiling.
- Tool activity and blocked actions are recorded in ticket audit logs.
- Ticket state and conversation history are persisted by ticket ID.
- A refund is only reported as issued when the refund tool confirms the ledger write.

The authoritative business rules are maintained in [`data/refund_policy.md`](data/refund_policy.md).

## Portfolio Demonstration

The dashboard includes illustrative sample tickets to demonstrate the operations interface, ticket statuses, and customer-support scenarios.

These sample records are frontend demonstration data. They are separate from the backend's persisted tickets and refund ledger. They should not be interpreted as actual customer transactions or confirmed refund activity.

The backend and agent workflow remain available for local demonstrations when the required AWS and API configuration is supplied.

## Reset Local Test Data

The project includes a reset script that clears generated test state and restores the seed refund ledger.

Read the script before running it:

```bash
uv run python starter/reset_lab.py
```

Do not run the reset while a ticket is actively being used.

## Current Scope and Limitations

This is a local portfolio and classwork demonstration, not a production-ready customer support platform.

- The HTTP API keeps active agent objects in process memory while Strands persists sessions to disk.
- Run a single API worker; multiple workers would not share in-memory agent locks.
- The supervisor token is a local demonstration control, not a replacement for a production identity provider, role system, or secrets manager.
- Customer and order details are retrieved through Ada's verified workflow rather than fabricated by the agent.
- Production deployment would require additional authentication, authorization, monitoring, infrastructure, and operational safeguards.

---

**Kora Home Refund Desk — Ada**  
*AI-assisted customer support with policy-driven refund controls and human oversight.*