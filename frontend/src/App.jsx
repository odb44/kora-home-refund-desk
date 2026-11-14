
import { useEffect, useState } from "react";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Bell,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Clock3,
  Command,
  CreditCard,
  FileText,
  Headphones,
  LayoutDashboard,
  LifeBuoy,
  MessageSquare,
  MoreHorizontal,
  Search,
  Send,
  Settings,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Wallet,
  X,
} from "lucide-react";
import "./index.css";
import { DEMO_TICKETS } from "./data/demoTickets.js";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const money = (value) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value);

function StatusBadge({ status }) {
  const styles = {
    "Pending review": "status-pending",
    "Needs approval": "status-approval",
    "In progress": "status-progress",
    Resolved: "status-resolved",
    Escalated: "status-escalated",
  };

  return (
    <span className={`status-badge ${styles[status] || "status-progress"}`}>
      <span className="status-dot" />
      {status}
    </span>
  );
}

function Avatar({ ticket, small = false }) {
  return (
    <div
      className={`avatar avatar-${ticket.color} ${small ? "avatar-small" : ""}`}
    >
      {ticket.initials}
    </div>
  );
}

function MetricCard({ label, value, change, icon: Icon, tone, trend }) {
  return (
    <div className="metric-card">
      <div className="metric-top">
        <span>{label}</span>
        <span className={`metric-icon ${tone}`}>
          <Icon size={18} />
        </span>
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-foot">
        <span className={`metric-change ${trend === "down" ? "negative" : ""}`}>
          {trend === "down" ? (
            <ArrowDownRight size={14} />
          ) : (
            <ArrowUpRight size={14} />
          )}
          {change}
        </span>
        <span>Workspace overview</span>
      </div>
    </div>
  );
}

export default function App() {
  const [tickets, setTickets] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All tickets");
  const [activeNav, setActiveNav] = useState("Overview");
  const [activity, setActivity] = useState([]);
  const [notice, setNotice] = useState("");
  const [showActivity, setShowActivity] = useState(true);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [apiConnected, setApiConnected] = useState(false);

  const selected = tickets.find((ticket) => ticket.id === selectedId);

  async function loadTickets() {
    try {
      const response = await fetch(`${API_BASE}/api/tickets`);
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      setApiConnected(true);
      const data = await response.json();
      const liveRows = (data.items || []).map((item) => ({
        id: item.ticket_id,
        name: item.customer_id || "Unverified customer",
        initials: "?",
        color: "blue",
        subject: item.subject || "Refund support request",
        order: (item.orders_discussed || [])[0] || "Not yet identified",
        product: "To be confirmed",
        amount: Number(item.total_refunded || 0),
        amountLabel: "Confirmed refund total",
        date: item.created_at ? new Date(item.created_at).toLocaleDateString() : "—",
        time: item.created_at ? new Date(item.created_at).toLocaleTimeString() : "—",
        sortDate: item.created_at || "1970-01-01T00:00:00Z",
        status: item.status === "closed" ? "Resolved" : item.status === "escalated" ? "Escalated" : "In progress",
        reason: "To be established with Ada",
        email: "Verified during conversation",
        payment: "Retrieved after verification",
        risk: "Not assessed",
        isDemo: false,
      }));
      const rows = [...DEMO_TICKETS, ...liveRows].sort(
        (a, b) => new Date(b.sortDate) - new Date(a.sortDate),
      );
      setTickets(rows);
      if (!selectedId && rows.length) setSelectedId(rows[0].id);
      if (selectedId && !rows.some((row) => row.id === selectedId)) setSelectedId(rows[0]?.id || null);
    } catch (error) {
      setApiConnected(false);
      setTickets(DEMO_TICKETS);
      if (!selectedId && DEMO_TICKETS.length) setSelectedId(DEMO_TICKETS[0].id);
      setNotice(`API unavailable — showing portfolio sample data. ${error.message}`);
    } finally { setLoading(false); }
  }

  useEffect(() => { loadTickets(); }, []); // Initial queue load only.

  async function loadTicketMessages(ticketId) {
    if (!ticketId) { setMessages([]); return; }
    const current = tickets.find((ticket) => ticket.id === ticketId);
    if (current?.isDemo) {
      setMessages(current.demoMessages || []);
      return;
    }
    try {
      const response = await fetch(`${API_BASE}/api/tickets/${ticketId}/messages`);
      if (!response.ok) return;
      const data = await response.json();
      setMessages(data.items || []);
    } catch { setMessages([]); }
  }

  async function loadTicketActivity(ticketId) {
    if (!ticketId) { setActivity([]); return; }
    const current = tickets.find((ticket) => ticket.id === ticketId);
    if (current?.isDemo) {
      setActivity(current.demoActivity || []);
      return;
    }
    try {
      const response = await fetch(`${API_BASE}/api/tickets/${ticketId}/activity`);
      if (!response.ok) return;
      const data = await response.json();
      setActivity((data.items || []).map((event) => ({
        type: event.status === "blocked" ? "warning" : event.status === "success" ? "success" : "info",
        title: event.event || event.tool || event.hook || "Agent activity",
        detail: event.output_preview || event.status || "Recorded by the backend audit log",
        time: event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "Recorded",
      })));
    } catch { setActivity([]); }
  }

  useEffect(() => {
    setMessages([]);
    loadTicketMessages(selectedId);
    loadTicketActivity(selectedId);
  }, [selectedId]);

  async function createTicket() {
    const subject = window.prompt("Briefly describe the refund request:");
    if (!subject || !subject.trim()) return;
    try {
      const response = await fetch(`${API_BASE}/api/tickets`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject: subject.trim() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not create ticket");
      await loadTickets(); setSelectedId(data.ticket_id);
      setNotice(`Ticket ${data.ticket_id} created.`);
    } catch (error) { setNotice(error.message); }
  }

  async function sendMessage(event) {
    event?.preventDefault();
    if (!selected || selected.isDemo || !draft.trim() || sending) return;
    const message = draft.trim();
    setMessages((items) => [...items, { role: "customer", content: message }]);
    setDraft(""); setSending(true);
    try {
      const response = await fetch(`${API_BASE}/api/tickets/${selected.id}/messages`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Ada could not respond");
      setMessages((items) => [...items, { role: "ada", content: data.reply || "Ada returned no text response." }]);
      setActivity((data.activity || []).map((event) => ({ type: "info", title: event.tool || event.event || "Agent activity", detail: event.output_preview || event.status || "Recorded", time: "Just now" })));
      await loadTickets();
    } catch (error) {
      setMessages((items) => [...items, { role: "system", content: error.message }]);
    } finally { setSending(false); }
  }

  async function closeSelectedTicket() {
    if (!selected || selected.isDemo) return;
    try {
      const response = await fetch(`${API_BASE}/api/tickets/${selected.id}/close`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not close ticket");
      setNotice(`Ticket ${selected.id} closed and summary saved.`);
      await loadTickets();
    } catch (error) { setNotice(error.message); }
  }

  const filteredTickets = tickets.filter((ticket) => {
    const search = query.toLowerCase();
    const matchesSearch =
      ticket.id.toLowerCase().includes(search) ||
      ticket.name.toLowerCase().includes(search) ||
      ticket.subject.toLowerCase().includes(search) ||
      ticket.order.toLowerCase().includes(search);

    const matchesFilter =
      filter === "All tickets" ||
      (filter === "Open" && ticket.status !== "Resolved") ||
      (filter === "Pending review" && ticket.status === "Pending review") ||
      (filter === "Resolved" && ticket.status === "Resolved") ||
      (filter === "Needs approval" && ticket.status === "Needs approval");

    return matchesSearch && matchesFilter;
  });

  const pendingCount = tickets.filter(
    (ticket) => ticket.status === "Pending review",
  ).length;
  const approvalCount = tickets.filter(
    (ticket) => ticket.status === "Needs approval",
  ).length;
  const resolvedCount = tickets.filter(
    (ticket) => ticket.status === "Resolved",
  ).length;
  const refundedTotal = tickets
    .filter((ticket) => !ticket.isDemo && ticket.status === "Resolved")
    .reduce((total, ticket) => total + ticket.amount, 0);

  async function updateStatus(status) {
    if (!selected || selected.isDemo) return;
    if (status === "Resolved") { closeSelectedTicket(); return; }
    try {
      const response = await fetch(`${API_BASE}/api/tickets/${selected.id}/escalate`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not escalate ticket");
      setNotice(`Ticket ${selected.id} escalated for supervisor review.`);
      await loadTickets();
      loadTicketActivity(selected.id);
    } catch (error) { setNotice(error.message); }
  }

  function handleNav(label) {
    setActiveNav(label);
    if (label === "Overview" || label === "Refund tickets") {
      setFilter("All tickets");
    } else if (label === "Approvals") {
      setFilter("Needs approval");
    } else if (label === "Audit logs") {
      setShowActivity(true);
      setNotice("Showing recorded backend audit events.");
      window.setTimeout(() => setNotice(""), 3000);
    } else {
      setNotice(`${label} is a UI preview in this demo.`);
      window.setTimeout(() => setNotice(""), 3000);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Command size={22} strokeWidth={2.5} />
          </div>
          <div>
            <div className="brand-name">kora<span>.</span></div>
            <div className="brand-caption">HOME OPERATIONS</div>
          </div>
        </div>

        <div className="workspace-switch">
          <div className="workspace-icon"><Headphones size={17} /></div>
          <div className="workspace-copy">
            <strong>Support workspace</strong>
            <span>Refund operations</span>
          </div>
          <ChevronDown size={15} className="muted-icon" />
        </div>

        <div className="nav-section-label">WORKSPACE</div>
        <nav className="nav-list">
          {[
            { label: "Overview", icon: LayoutDashboard },
            { label: "Refund tickets", icon: MessageSquare, count: tickets.length },
            { label: "Approvals", icon: ShieldCheck, count: approvalCount },
            { label: "Orders", icon: ShoppingBag },
            { label: "Customers", icon: Headphones },
          ].map(({ label, icon: Icon, count }) => (
            <button
              key={label}
              className={`nav-item ${activeNav === label ? "nav-active" : ""}`}
              onClick={() => handleNav(label)}
            >
              <Icon size={18} />
              <span>{label}</span>
              {count > 0 && <span className="nav-count">{count}</span>}
            </button>
          ))}
        </nav>

        <div className="nav-section-label nav-label-spaced">MANAGEMENT</div>
        <nav className="nav-list">
          {[
            { label: "Audit logs", icon: FileText },
            { label: "Agent activity", icon: Activity },
            { label: "Settings", icon: Settings },
          ].map(({ label, icon: Icon }) => (
            <button
              key={label}
              className={`nav-item ${activeNav === label ? "nav-active" : ""}`}
              onClick={() => handleNav(label)}
            >
              <Icon size={18} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="help-card">
            <div className="help-icon"><LifeBuoy size={19} /></div>
            <strong>Need a hand?</strong>
            <p>Visit the support centre for help with your workspace.</p>
            <button onClick={() => handleNav("Help centre")}>
              Visit help centre <ChevronRight size={14} />
            </button>
          </div>
          <div className="user-profile">
            <div className="profile-avatar">OB</div>
            <div className="profile-copy">
              <strong>Operations Admin</strong>
              <span>Administrator</span>
            </div>
            <MoreHorizontal size={19} className="muted-icon" />
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <ChevronRight size={14} />
            <strong>{activeNav}</strong>
          </div>
          <div className="topbar-right">
            <div className={`system-status ${apiConnected ? "is-connected" : "is-offline"}`}>
              <span className="live-dot" /> {apiConnected ? "API connected" : loading ? "Connecting to API" : "Sample mode · API offline"}
            </div>
            <button
              className="icon-button notification-button"
              aria-label="Notifications"
              onClick={() => {
                setNotice("You're all caught up on notifications.");
                window.setTimeout(() => setNotice(""), 3000);
              }}
            >
              <Bell size={18} />
              <span />
            </button>
            <div className="topbar-divider" />
            <div className="mini-profile">OB</div>
          </div>
        </header>

        <div className="page-content">
          <section className="welcome-row">
            <div>
              <div className="eyebrow"><span className="eyebrow-line" /> LOCAL REFUND OPERATIONS</div>
              <h1>Refund desk <span className="wave">✳</span></h1>
              <p className="page-subtitle">
                Here's what's happening with your customer refunds today.
              </p>
            </div>
            <div className="welcome-actions">
              <button className="button button-secondary" onClick={() => {
                setShowActivity(!showActivity);
              }}>
                <Activity size={16} /> Activity
              </button>
              <button className="button button-primary" onClick={createTicket}>
                <MessageSquare size={16} /> New ticket
              </button>
              <button className="button button-secondary" onClick={() => {
                setQuery("");
                setFilter("All tickets");
                setActiveNav("Refund tickets");
                document.getElementById("ticket-queue")?.scrollIntoView({ behavior: "smooth" });
              }}>
                <MessageSquare size={16} /> View tickets <ChevronRight size={15} />
              </button>
            </div>
          </section>

          {notice && (
            <div className="toast-message">
              <Check size={16} /> {notice}
              <button aria-label="Dismiss" onClick={() => setNotice("")}><X size={15} /></button>
            </div>
          )}

          <section className="metrics-grid">
            <MetricCard
              label="Total tickets"
              value={String(tickets.length).padStart(2, "0")}
              change="Live queue"
              icon={MessageSquare}
              tone="metric-purple"
            />
            <MetricCard
              label="Pending review"
              value={String(pendingCount).padStart(2, "0")}
              change={`${pendingCount} open tickets`}
              icon={Clock3}
              tone="metric-amber"
              trend="down"
            />
            <MetricCard
              label="Resolved tickets"
              value={String(resolvedCount).padStart(2, "0")}
              change="Closed tickets"
              icon={Check}
              tone="metric-green"
            />
            <MetricCard
              label="Refund value"
              value={money(refundedTotal)}
              change="Confirmed refunds"
              icon={Wallet}
              tone="metric-blue"
            />
          </section>

          <section className="insight-banner">
            <div className="insight-sparkle"><Sparkles size={20} /></div>
            <div className="insight-copy">
              <div><strong>Ada's daily insight</strong><span className="ai-pill">AI ASSISTANT</span></div>
              <p>
                {approvalCount > 0
                  ? `${approvalCount} ticket${approvalCount > 1 ? "s need" : " needs"} approval. Review the queue to keep refunds moving.`
                  : "Your queue is looking good. Keep an eye on incoming refund requests."}
              </p>
            </div>
            <button onClick={() => {
              setFilter("Needs approval");
              setActiveNav("Approvals");
              document.getElementById("ticket-queue")?.scrollIntoView({ behavior: "smooth" });
            }}>
              Review approvals <ChevronRight size={15} />
            </button>
          </section>

          <section className="work-grid">
            <div className="panel ticket-panel" id="ticket-queue">
              <div className="panel-heading">
                <div>
                  <h2>Refund tickets <span className="heading-count">{tickets.length}</span></h2>
                  <p>Review and manage customer refund requests.</p>
                </div>
                <button
                  className="icon-button"
                  aria-label="Refresh ticket queue"
                  onClick={() => {
                    setQuery("");
                    setFilter("All tickets");
                    loadTickets();
                    setNotice("Ticket queue refreshed.");
                    window.setTimeout(() => setNotice(""), 3000);
                  }}
                >
                  <Activity size={17} />
                </button>
              </div>

              <div className="queue-controls">
                <div className="search-box">
                  <Search size={16} />
                  <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search tickets..."
                    aria-label="Search tickets"
                  />
                  {query && <button onClick={() => setQuery("")} aria-label="Clear search"><X size={14} /></button>}
                </div>
                <div className="filter-wrap">
                  <select
                    value={filter}
                    onChange={(event) => setFilter(event.target.value)}
                    aria-label="Filter tickets"
                  >
                    <option>All tickets</option>
                    <option>Open</option>
                    <option>Pending review</option>
                    <option>Needs approval</option>
                    <option>Resolved</option>
                  </select>
                  <ChevronDown size={14} />
                </div>
              </div>

              <div className="ticket-list">
                {loading && <div className="empty-state">Loading tickets from the backend…</div>}
                {!loading && filteredTickets.length === 0 && (
                  <div className="empty-state">
                    <MessageSquare size={24} />
                    <strong>No tickets yet</strong>
                    <span>Create a ticket to start a conversation with Ada.</span>
                    <button onClick={createTicket}>Create ticket</button>
                  </div>
                )}
                {filteredTickets.map((ticket) => (
                  <button
                    key={ticket.id}
                    className={`ticket-row ${selectedId === ticket.id ? "ticket-selected" : ""}`}
                    onClick={() => setSelectedId(ticket.id)}
                  >
                    <Avatar ticket={ticket} />
                    <div className="ticket-main">
                      <div className="ticket-title-row">
                        <strong>{ticket.name}</strong>
                        <span className="ticket-id">{ticket.id}</span>
                        {ticket.isDemo && <span className="demo-record-tag">SAMPLE</span>}
                      </div>
                      <div className="ticket-subject">{ticket.subject}</div>
                      <div className="ticket-meta">
                        <span>{ticket.order}</span><span className="meta-separator">·</span>
                        <span>{ticket.date}</span>
                      </div>
                    </div>
                    <div className="ticket-end">
                      <strong>{money(ticket.amount)}</strong>
                      <StatusBadge status={ticket.status} />
                    </div>
                  </button>
                ))}
              </div>

              <div className="queue-footer">
                <span>Showing <strong>{filteredTickets.length}</strong> of {tickets.length} tickets</span>
                <div className="pagination">
                  <button aria-label="Previous page" disabled><ChevronLeft size={16} /></button>
                  <button className="page-number">1</button>
                  <button aria-label="Next page" disabled><ChevronRight size={16} /></button>
                </div>
              </div>
            </div>

            <div className="right-column">
              {selected ? (
                <div className="panel detail-panel">
                  <div className="panel-heading detail-heading">
                    <div>
                      <div className="detail-kicker">TICKET DETAILS</div>
                      <h2>{selected.id}</h2>
                    </div>
                    <button className="icon-button" aria-label="More ticket options" onClick={() => {
                      setNotice("Additional ticket options will be available in the connected backend.");
                      window.setTimeout(() => setNotice(""), 3000);
                    }}><MoreHorizontal size={19} /></button>
                  </div>

                  <div className="detail-customer">
                    <Avatar ticket={selected} />
                    <div>
                      <strong>{selected.name}</strong>
                      <span>{selected.email}</span>
                      {selected.isDemo && <span className="demo-record-note">Portfolio sample · not a live customer interaction</span>}
                    </div>

                  </div>

                  <div className="detail-status-line">
                    <StatusBadge status={selected.status} />
                    <span>Created {selected.time}</span>
                  </div>

                  <div className="detail-divider" />

                  <div className="detail-section-title">ORDER INFORMATION</div>
                  <div className="info-row">
                    <span>Order number</span>
                    <strong className="link-text">{selected.order}</strong>
                  </div>
                  <div className="info-row">
                    <span>Product</span>
                    <strong>{selected.product}</strong>
                  </div>
                  <div className="info-row">
                    <span>Payment method</span>
                    <strong><CreditCard size={14} /> {selected.payment}</strong>
                  </div>
                  <div className="info-row">
                    <span>Refund reason</span>
                    <strong>{selected.reason}</strong>
                  </div>

                  <div className="refund-amount-card">
                    <div>
                      <span>{selected.isDemo ? "Illustrative order value" : selected.amountLabel || "Confirmed refund total"}</span>
                      <strong>{money(selected.amount)}</strong>
                    </div>
                    <div className="refund-amount-icon"><Wallet size={20} /></div>
                  </div>

                  <div className="risk-line">
                    <ShieldCheck size={16} />
                    <span>Risk assessment</span>
                    <strong className={selected.risk === "Medium risk" ? "risk-medium" : ""}>{selected.risk}</strong>
                  </div>

                  <div className="detail-divider" />

                  <div className="detail-section-title">REVIEW ACTIONS</div>
                  <div className="action-buttons">
                    <button
                      className="button button-primary action-main"
                      disabled={selected.isDemo || selected.status === "Resolved"}
                      onClick={() => updateStatus("Resolved", "Refund marked resolved", `${selected.id} marked resolved in the demo.`)}
                    >
                      <Check size={16} /> Close ticket
                    </button>
                    <button
                      className="button button-secondary action-secondary"
                      disabled={selected.isDemo || selected.status === "Escalated" || selected.status === "Resolved"}
                      onClick={() => updateStatus("Escalated", "Ticket escalated", `${selected.id} flagged for human review.`)}
                    >
                      <CircleAlert size={16} /> Escalate
                    </button>
                  </div>
                  <p className="demo-warning"><ShieldCheck size={13} /> {selected.isDemo ? "Sample record only. No refund, approval or ledger entry has been created." : "Refund decisions and approvals are enforced by the backend."}</p>

                  <div className="detail-divider" />
                  <div className="detail-section-title">CONVERSATION WITH ADA</div>
                  <div className="ada-chat-history">
                    {selected.isDemo && <p className="chat-placeholder">Illustrative conversation for portfolio preview. Start a new ticket to interact with Ada live.</p>}
                    {!selected.isDemo && messages.length === 0 && <p className="chat-placeholder">Start the conversation. Ada will verify the customer before discussing order information.</p>}
                    {messages.map((message, index) => (
                      <div className={`chat-message chat-${message.role}`} key={`${message.role}-${index}`}>
                        <strong>{message.role === "customer" ? "You" : message.role === "ada" ? "Ada" : "System"}</strong>
                        <p>{message.content}</p>
                      </div>
                    ))}
                    {sending && <div className="chat-placeholder">Ada is thinking…</div>}
                  </div>
                  <form className="ada-chat-form" onSubmit={sendMessage}>
                    <input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder={selected.isDemo ? "Demo conversation · create a live ticket to chat" : "Message Ada…"} disabled={selected.isDemo || sending || selected.status === "Resolved"} />
                    <button className="button button-primary" type="submit" disabled={selected.isDemo || sending || !draft.trim() || selected.status === "Resolved"}><Send size={15} /></button>
                  </form>
                  {!selected.isDemo && <button className="text-button close-ticket-button" onClick={closeSelectedTicket} disabled={selected.status === "Resolved"}>Close ticket & generate summary</button>}
                </div>
              ) : (
                <div className="panel empty-detail">Select a ticket to view its details.</div>
              )}

              {showActivity && (
                <div className="panel activity-panel">
                  <div className="panel-heading activity-heading">
                    <div>
                      <h2><span className="activity-live-dot" /> Ada's activity</h2>
                      <p>Recent agent events</p>
                    </div>
                    <button className="text-button" onClick={() => setActivity([])}>Clear</button>
                  </div>
                  {activity.length > 0 ? (
                    <div className="activity-list">
                      {activity.map((event, index) => (
                        <div className="activity-item" key={`${event.title}-${index}`}>
                          <div className={`activity-icon activity-${event.type}`}>
                            {event.type === "success" ? <Check size={14} /> : event.type === "warning" ? <CircleAlert size={14} /> : <Activity size={14} />}
                          </div>
                          <div className="activity-content">
                            <strong>{event.title}</strong>
                            <p>{event.detail}</p>
                            <span>{event.time}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="activity-empty">No events to show.</div>
                  )}
                  <div className="activity-bottom">
                    <span><span className="live-dot" /> Backend audit events</span>
                    <button onClick={() => setShowActivity(false)}>Hide feed <ChevronRight size={14} /></button>
                  </div>
                </div>
              )}
            </div>
          </section>

          <footer className="page-footer">
            <span>© 2026 Kora Home · Refund operations</span>
            <span><span className="footer-status-dot" /> Local API environment</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
