import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

function getPriorityColor(p) {
  if (!p) return "bg-zinc-800 text-zinc-400";
  const dim = p.toLowerCase();
  if (dim.includes("emergency") || dim.includes("asap")) return "bg-red-500/10 text-red-400 border border-red-500/20";
  if (dim.includes("high")) return "bg-orange-500/10 text-orange-400 border border-orange-500/20";
  if (dim.includes("medium")) return "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20";
  return "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
}

function getScoreColor(s) {
  if (s === undefined || s === null) return "text-zinc-500";
  if (s >= 80) return "text-emerald-400 font-bold";
  if (s >= 50) return "text-yellow-400";
  return "text-zinc-500";
}

function Badge({ children, className = "" }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${className}`}>
      {children}
    </span>
  );
}

function getStatusBadge(status) {
  if (status === "qualified") {
    return <Badge className="bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">Qualified</Badge>;
  }
  if (status === "lost") {
    return <Badge className="bg-red-500/10 text-red-300 border border-red-500/20">Lost</Badge>;
  }
  return <Badge className="bg-zinc-800 text-zinc-400 border border-zinc-700/50">Open</Badge>;
}

function ActionButton({ onClick, color, icon, title, description }) {
  const colors = {
    emerald: "border-emerald-500/20 bg-emerald-500/5 hover:bg-emerald-500/10 text-emerald-200",
    red: "border-red-500/20 bg-red-500/5 hover:bg-red-500/10 text-red-200",
    blue: "border-blue-500/20 bg-blue-500/5 hover:bg-blue-500/10 text-blue-200",
    amber: "border-amber-500/20 bg-amber-500/5 hover:bg-amber-500/10 text-amber-200",
  };

  return (
    <button
      onClick={onClick}
      className={`flex flex-col items-start p-4 rounded-xl border transition-all w-full text-left ${colors[color]}`}
    >
      <div className="flex items-center gap-2 mb-1">
        <span>{icon}</span>
        <span className="font-semibold text-sm">{title}</span>
      </div>
      <span className="text-xs opacity-70">{description}</span>
    </button>
  );
}

function AdminLeadsSection() {
  const [token, setToken] = useState("");
  const [limit, setLimit] = useState(50);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [rows, setRows] = useState([]);
  const [selectedLead, setSelectedLead] = useState(null);
  const [actionError, setActionError] = useState("");

  async function loadLeads() {
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/admin/leads?limit=${limit}`, {
        headers: { "x-task-token": token },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.detail || "Failed to load leads.");
      }
      setRows(data.items || []);
    } catch (err) {
      setError(err?.message || "Failed to load leads.");
    } finally {
      setLoading(false);
    }
  }

  async function runAction(id, path, payload) {
    setActionError("");
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-task-token": token,
        },
        body: JSON.stringify(payload || {}),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.detail || "Action failed.");
      }
      await loadLeads();
      // Keep drawer open but update data? Or close it? Let's close it on success for now, or refresh selected lead.
      // For now, let's close it to signify completion.
      setSelectedLead(null);
    } catch (err) {
      setActionError(err?.message || "Action failed.");
    }
  }

  function promptRequestDetails(id) {
    const message = window.prompt("Message to request details (optional):", "");
    if (message === null) return;
    runAction(id, `/admin/leads/${id}/request-details`, { message });
  }

  function promptFollowUp(id) {
    const input = window.prompt("Follow-up in how many hours?", "48");
    if (!input) return;
    const hours = Number(input);
    if (Number.isNaN(hours) || hours < 1) {
      setActionError("Please provide a valid number of hours.");
      return;
    }
    runAction(id, `/admin/leads/${id}/follow-up`, { hours });
  }

  return (
    <section className="magnio-section relative min-h-screen overflow-hidden bg-zinc-950">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-24 left-1/2 h-80 w-[50rem] -translate-x-1/2 rounded-full bg-blue-500/5 blur-3xl" />
        <div className="absolute top-0 right-0 h-96 w-96 rounded-full bg-indigo-500/5 blur-3xl" />
        <div className="absolute bottom-0 left-0 h-96 w-96 rounded-full bg-purple-500/5 blur-3xl" />
      </div>
      <div className="magnio-container">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
          <div>
            <h1 className="text-3xl md:text-4xl font-display font-bold text-white tracking-tight mb-2">
              Admin Leads
            </h1>
            <p className="text-zinc-400">Secure view for lead triage and management.</p>
          </div>

          <div className="flex bg-zinc-900/50 p-2 rounded-xl border border-zinc-800/50 backdrop-blur-sm gap-2">
            <input
              type="password"
              className="bg-transparent border-none text-sm text-white placeholder-zinc-600 focus:ring-0 w-32 md:w-48 px-3"
              placeholder="Access Token"
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
            <div className="w-px bg-zinc-800 my-1"></div>
            <input
              type="number"
              className="bg-transparent border-none text-sm text-white placeholder-zinc-600 focus:ring-0 w-16 px-3 text-center"
              placeholder="50"
              min="1"
              max="500"
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
            />
            <button
              className="bg-zinc-100 hover:bg-white text-zinc-950 text-xs font-bold px-4 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={loadLeads}
              disabled={loading || !token}
            >
              {loading ? "..." : "Refresh"}
            </button>
          </div>
        </div>

        {error ? (
          <div className="mb-8 rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-200 flex items-center gap-3">
            <svg className="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            {error}
          </div>
        ) : null}

        <div className="magnio-card overflow-hidden">
          {rows.length === 0 && !loading ? (
            <div className="p-12 text-center text-zinc-500 text-sm">
              No leads loaded. Enter token to view data.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-900/50 text-xs uppercase text-zinc-500 font-medium">
                  <tr>
                    <th className="px-6 py-4 font-semibold">Date</th>
                    <th className="px-6 py-4 font-semibold">Contact</th>
                    <th className="px-6 py-4 font-semibold">Company</th>
                    <th className="px-6 py-4 font-semibold">Priority</th>
                    <th className="px-6 py-4 font-semibold">Score</th>
                    <th className="px-6 py-4 font-semibold">Status</th>
                    <th className="px-6 py-4 font-semibold">Cal.com</th>
                    <th className="px-6 py-4 font-semibold w-10"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {rows.map((row) => (
                    <tr
                      key={row.id}
                      onClick={() => setSelectedLead(row)}
                      className="group hover:bg-white/[0.02] transition-colors cursor-pointer"
                    >
                      <td className="px-6 py-4 whitespace-nowrap text-zinc-400 text-xs font-mono">
                        {new Date(row.createdAtIso || row.createdAt).toLocaleDateString()}
                        <div className="text-zinc-600">{new Date(row.createdAtIso || row.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="font-medium text-zinc-200">{row.name || "Unknown"}</div>
                        <div className="text-xs text-zinc-500 font-mono mt-0.5">{row.email}</div>
                      </td>
                      <td className="px-6 py-4 text-zinc-300">
                        {row.company || <span className="text-zinc-600 italic">None</span>}
                      </td>
                      <td className="px-6 py-4">
                        <Badge className={getPriorityColor(row.priority)}>
                          {row.priority || "Normal"}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 font-mono">
                        <span className={getScoreColor(row.score)}>{row.score ?? "-"}</span>
                        {row.tier && <span className="ml-2 text-xs text-zinc-500 border border-zinc-800 px-1.5 py-0.5 rounded tracking-wide">{row.tier}</span>}
                      </td>
                      <td className="px-6 py-4 text-zinc-400">
                        {getStatusBadge(row.status)}
                        <div className="text-xs text-zinc-600 mt-2">{row.requestStatus || "-"}</div>
                        <div className="text-xs text-zinc-600 mt-0.5">{row.nextAction}</div>
                      </td>
                      <td className="px-6 py-4">
                        {row.calcomStatus ? (
                          <span className="inline-flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-500/5 px-2 py-1 rounded border border-emerald-500/10">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                            {row.calcomStatus}
                          </span>
                        ) : <span className="text-zinc-600 text-xs">-</span>}
                      </td>
                      <td className="px-6 py-4 text-zinc-600">
                        <svg className="w-5 h-5 group-hover:text-zinc-400 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Side Drawer */}
        {/* Side Drawer */}
        <AnimatePresence>
          {selectedLead && (
            <>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
                onClick={() => setSelectedLead(null)}
              />
              <motion.div
                initial={{ x: "100%" }}
                animate={{ x: 0 }}
                exit={{ x: "100%" }}
                transition={{ type: "spring", damping: 30, stiffness: 300 }}
                className="fixed inset-y-0 right-0 w-full max-w-md bg-zinc-950 border-l border-zinc-800 shadow-2xl z-50 overflow-y-auto"
              >
                <div className="p-6">
                  <div className="flex items-start justify-between mb-8">
                    <div>
                      <h2 className="text-2xl font-display font-bold text-white mb-1">{selectedLead.name}</h2>
                      <div className="flex items-center gap-2">
                        <span className="text-zinc-400 text-sm">{selectedLead.email}</span>
                        <Badge className={getPriorityColor(selectedLead.priority)}>{selectedLead.priority || "Normal"}</Badge>
                      </div>
                    </div>
                    <button
                      onClick={() => setSelectedLead(null)}
                      className="p-2 -mr-2 text-zinc-500 hover:text-zinc-300 transition-colors"
                    >
                      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>

                  <div className="space-y-6">
                    <div className="bg-zinc-900/50 p-4 rounded-xl border border-zinc-800/50">
                      <h3 className="text-xs uppercase text-zinc-500 font-semibold mb-3">Lead Details</h3>
                      <dl className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <dt className="text-zinc-400">Company</dt>
                          <dd className="text-zinc-200 font-medium">{selectedLead.company || "-"}</dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-zinc-400">Score</dt>
                          <dd className="text-zinc-200 font-medium">{selectedLead.score || "-"}</dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-zinc-400">Timeline</dt>
                          <dd className="text-zinc-200 font-medium">{selectedLead.timeline || "-"}</dd>
                        </div>
                      </dl>
                    </div>

                    <div>
                      <h3 className="text-xs uppercase text-zinc-500 font-semibold mb-3">Expensive Problem</h3>
                      <div className="bg-zinc-900/30 p-4 rounded-xl border border-zinc-800/30 text-zinc-300 text-sm leading-relaxed">
                        {selectedLead.problem || selectedLead.goals || "No details provided."}
                      </div>
                    </div>

                    <div className="border-t border-zinc-800 pt-6">
                      <h3 className="text-xs uppercase text-zinc-500 font-semibold mb-4">Actions</h3>
                      <div className="grid grid-cols-1 gap-3">
                        <ActionButton
                          color="emerald"
                          icon="✅"
                          title="Mark Qualified"
                          description="Move to deal pipeline."
                          onClick={() => {
                            if (window.confirm("Mark as qualified?")) runAction(selectedLead.id, `/admin/leads/${selectedLead.id}/status`, { status: "qualified" })
                          }}
                        />
                        <ActionButton
                          color="red"
                          icon="🚫"
                          title="Mark Lost"
                          description="Archive this lead."
                          onClick={() => {
                            if (window.confirm("Mark as lost?")) runAction(selectedLead.id, `/admin/leads/${selectedLead.id}/status`, { status: "lost" })
                          }}
                        />
                        <div className="pt-2 grid grid-cols-2 gap-3">
                          <ActionButton
                            color="blue"
                            icon="📬"
                            title="Request Details"
                            description="Send email inquiry."
                            onClick={() => promptRequestDetails(selectedLead.id)}
                          />
                          <ActionButton
                            color="amber"
                            icon="⏰"
                            title="Follow Up"
                            description="Schedule reminder."
                            onClick={() => promptFollowUp(selectedLead.id)}
                          />
                        </div>
                      </div>

                      {actionError && (
                        <div className="mt-4 text-xs text-red-300 bg-red-500/10 p-2 rounded border border-red-500/20">
                          {actionError}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </motion.div>
            </>
          )}
        </AnimatePresence>
      </div>
    </section>
  );
}

export default AdminLeadsSection;
