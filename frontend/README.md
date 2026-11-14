# Kora Home Refund Desk — Frontend

The Kora Home Refund Desk frontend is a React 19 and Vite operations dashboard for Ada, an AI-assisted refund support agent.

It provides an interface for viewing and managing refund-support tickets, following customer conversations, reviewing ticket activity, and handling escalations.

The frontend connects to the local FastAPI adapter, which communicates with the underlying Ada agent.

## Technology Stack

- React 19
- Vite
- JavaScript
- CSS
- Lucide React icons
- FastAPI backend integration

## Requirements

- Node.js 20.19+ or 22.12+
- The Python API running at `http://127.0.0.1:8000`

## Setup

From the `frontend` directory:

```bash
npm ci
npm run dev
```

Open the URL printed by Vite, normally:

`http://localhost:5173`

## API Configuration

The default API address is:

`http://127.0.0.1:8000`

To use another API address, create `frontend/.env.local`:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Restart the Vite development server after changing environment variables.

**Security note:** Never place AWS credentials, supervisor tokens, or other secrets in a `VITE_` variable. Vite exposes these values to the browser.

## Dashboard Features

The interface is designed around the day-to-day operations of a refund support desk.

- **Ticket Queue:** View and filter customer-support tickets.
- **Ticket Creation:** Create a new support ticket.
- **Ada Conversation:** Continue a conversation associated with a selected ticket.
- **Ticket Activity:** Review recorded backend audit events.
- **Escalation:** Escalate an open ticket for supervisor review.
- **Ticket Closure:** Close a ticket and request its structured summary.
- **Ticket Details:** Review the selected ticket's available information and status.

## Portfolio Demo Data

The dashboard includes illustrative sample tickets to make the interface presentable when demonstrating the portfolio project.

These examples cover different support scenarios, including:

- Damaged-item refund requests.
- High-value refund requests requiring approval review.
- Delivery disputes requiring escalation.
- Refund eligibility enquiries.

The sample records are frontend demonstration data. They are not actual customer tickets, do not represent confirmed refunds, and should not be treated as persisted backend transactions.

Live ticket operations depend on the FastAPI backend being available.

## Backend Integration

The frontend communicates with the local FastAPI adapter.

Start the backend from the project root:

```bash
uv run uvicorn starter.api:app --host 127.0.0.1 --port 8000 --reload
```

The frontend uses the API for ticket retrieval, ticket creation, Ada conversations, activity retrieval, escalation, and ticket closure.

See the root [`README.md`](../README.md) for backend configuration, API endpoints, and refund safety controls.

## Production and Security Considerations

This frontend is part of a local portfolio demonstration, not a deployed production support platform.

- Customer verification and refund decisions belong to the backend workflow.
- Refund calculations are handled by deterministic backend policy logic.
- Supervisor approval is enforced through the backend.
- Sensitive credentials must remain on the backend and must never be exposed in browser environment variables.
- The interface should not be treated as the authority for refund eligibility or payment status.

## Build

To generate a production frontend build:

```bash
npm run build
```

To preview the generated build locally:

```bash
npm run preview
```

---

**Kora Home Refund Desk — Ada**  
*An operations dashboard for AI-assisted customer refund support.*