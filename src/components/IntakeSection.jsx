import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

function parseQuery() {
  const hash = window.location.hash || "";
  if (hash.includes("?")) {
    return new URLSearchParams(hash.split("?")[1]);
  }
  if (window.location.search) {
    return new URLSearchParams(window.location.search.slice(1));
  }
  return new URLSearchParams();
}

function IntakeSection() {
  const params = parseQuery();
  const [form, setForm] = useState({
    leadId: params.get("leadId") || "",
    token: params.get("token") || "",
    email: params.get("email") || "",
    budgetRange: "",
    timeline: "",
    goals: "",
    constraints: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    const nextParams = parseQuery();
    setForm((prev) => ({
      ...prev,
      leadId: nextParams.get("leadId") || prev.leadId,
      token: nextParams.get("token") || prev.token,
      email: nextParams.get("email") || prev.email,
    }));
  }, []);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (!form.leadId.trim() || !form.token.trim() || !form.goals.trim()) {
      setError("Please complete required fields.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/intake`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          leadId: form.leadId.trim(),
          token: form.token.trim(),
          email: form.email.trim() || null,
          budgetRange: form.budgetRange || null,
          timeline: form.timeline || null,
          goals: form.goals,
          constraints: form.constraints || null,
        }),
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.detail || "Something went wrong. Please try again.");
      }

      setSuccess("Thanks - we'll review this before the call.");
      setForm((prev) => ({ ...prev, goals: "", constraints: "" }));
    } catch (err) {
      setError(err?.message || "Submission failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="magnio-section bg-zinc-950 min-h-screen">
      <div className="magnio-container">
        <div className="text-center mb-12">
          <h1 className="text-4xl sm:text-5xl font-display font-bold mb-4 text-white tracking-tight">
            Quick Intake
          </h1>
          <p className="text-lg text-zinc-400">
            Help us prepare for your call in 2 minutes.
          </p>
        </div>

        <div className="magnio-card p-8 sm:p-12 max-w-3xl mx-auto">
          <form className="space-y-6" onSubmit={onSubmit}>
            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <label htmlFor="leadId" className="magnio-label">
                  Lead ID
                </label>
                <input
                  type="text"
                  id="leadId"
                  name="leadId"
                  className="magnio-input"
                  placeholder="Paste your lead ID"
                  required
                  value={form.leadId}
                  onChange={(e) => setForm((prev) => ({ ...prev, leadId: e.target.value }))}
                />
              </div>
              <div>
                <label htmlFor="token" className="magnio-label">
                  Intake token
                </label>
                <input
                  type="text"
                  id="token"
                  name="token"
                  className="magnio-input"
                  placeholder="Paste your token"
                  required
                  value={form.token}
                  onChange={(e) => setForm((prev) => ({ ...prev, token: e.target.value }))}
                />
              </div>
              <div>
                <label htmlFor="email" className="magnio-label">
                  Email
                </label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  className="magnio-input"
                  placeholder="you@company.com"
                  value={form.email}
                  onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))}
                />
              </div>
            </div>

            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <label htmlFor="budgetRange" className="magnio-label">
                  Budget range (optional)
                </label>
                <input
                  type="text"
                  id="budgetRange"
                  name="budgetRange"
                  className="magnio-input"
                  placeholder="$10k–$50k"
                  value={form.budgetRange}
                  onChange={(e) => setForm((prev) => ({ ...prev, budgetRange: e.target.value }))}
                />
              </div>
              <div>
                <label htmlFor="timeline" className="magnio-label">
                  Timeline (optional)
                </label>
                <input
                  type="text"
                  id="timeline"
                  name="timeline"
                  className="magnio-input"
                  placeholder="Next 2–4 weeks"
                  value={form.timeline}
                  onChange={(e) => setForm((prev) => ({ ...prev, timeline: e.target.value }))}
                />
              </div>
            </div>

            <div>
              <label htmlFor="goals" className="magnio-label">
                Goals and desired outcome
              </label>
              <textarea
                rows="5"
                id="goals"
                name="goals"
                className="magnio-input resize-none"
                placeholder="What would success look like?"
                required
                value={form.goals}
                onChange={(e) => setForm((prev) => ({ ...prev, goals: e.target.value }))}
              ></textarea>
            </div>

            <div>
              <label htmlFor="constraints" className="magnio-label">
                Constraints or risks (optional)
              </label>
              <textarea
                rows="4"
                id="constraints"
                name="constraints"
                className="magnio-input resize-none"
                placeholder="Any blockers, compliance, deadlines?"
                value={form.constraints}
                onChange={(e) => setForm((prev) => ({ ...prev, constraints: e.target.value }))}
              ></textarea>
            </div>

            {error ? (
              <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                {error}
              </div>
            ) : null}

            {success ? (
              <div className="mt-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
                {success}
              </div>
            ) : null}

            <button
              type="submit"
              disabled={loading}
              className="w-full inline-flex items-center justify-center rounded-xl bg-gradient-to-r from-blue-600 to-blue-500 px-6 py-4 text-lg font-bold text-white transition-all hover:from-blue-500 hover:to-blue-400 hover:shadow-lg hover:shadow-blue-500/20 disabled:opacity-70 disabled:cursor-not-allowed"
            >
              {loading ? "Sending…" : "Submit Intake →"}
            </button>
          </form>
        </div>
      </div>
    </section>
  );
}

export default IntakeSection;
