import { useEffect, useRef, useState } from "react";
import { Send, CheckCircle2, Loader2, Mail, Linkedin, Github } from "lucide-react";
import SpotlightCard from "./SpotlightCard";
import RevealOnScroll from "./RevealOnScroll";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

const timelineOptions = [
  "ASAP (Emergency)",
  "1–2 weeks",
  "1 month",
  "2–3 months",
  "Exploratory (No rush)",
];

function InputField({ label, id, type = "text", placeholder, value, onChange, required = false }) {
  return (
    <div className="group">
      <label htmlFor={id} className="mb-2 block text-sm font-medium text-zinc-400 transition-colors group-focus-within:text-blue-400">
        {label}
      </label>
      <input
        type={type}
        id={id}
        name={id}
        className="w-full rounded-xl border border-zinc-800 bg-zinc-900/50 px-4 py-3 text-zinc-100 placeholder:text-zinc-600 outline-none transition-all focus:border-blue-500/50 focus:bg-zinc-900 focus:ring-4 focus:ring-blue-500/10"
        placeholder={placeholder}
        required={required}
        value={value}
        onChange={onChange}
      />
    </div>
  );
}

function formatSla(hours) {
  if (!hours) return "soon";
  if (hours <= 4) return "within a few hours";
  if (hours <= 24) return "within 24 hours";
  return `within ${hours} hours`;
}

function ContactSection() {
  const CONTACT_EMAIL = "hello@magnio.io";
  const LINKEDIN_URL = "https://www.linkedin.com/in/sebastian-rosales-3a83a851/";
  const GITHUB_URL = "https://github.com/sebasrosalesr";
  const CALCOM_URL = "https://cal.com/sebastian-rosales-iuyl0n/30min";

  const [form, setForm] = useState({
    name: "",
    email: "",
    company: "",
    problem: "",
    timeline: "ASAP (Emergency)",
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const successTimeoutRef = useRef(null);

  useEffect(() => {
    return () => {
      if (successTimeoutRef.current) {
        clearTimeout(successTimeoutRef.current);
      }
    };
  }, []);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (!form.name.trim() || !form.email.trim() || !form.problem.trim()) {
      setError("Please complete required fields.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/lead`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name,
          email: form.email,
          company: form.company || null,
          problem: form.problem,
          timeline: form.timeline,
        }),
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.detail || "Something went wrong. Please try again.");
      }

      setSuccess(`Got it — we’ll reply ${formatSla(data.slaHours)}.`);
      if (successTimeoutRef.current) {
        clearTimeout(successTimeoutRef.current);
      }
      successTimeoutRef.current = setTimeout(() => {
        setSuccess("");
      }, 40000);
      setForm((prev) => ({
        name: "",
        email: "",
        company: "",
        problem: "",
        timeline: prev.timeline,
      }));
    } catch (err) {
      setError(err?.message || "Submission failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section id="contact" className="magnio-section relative z-10">
      <div className="magnio-container max-w-5xl">
        <RevealOnScroll>
          <div className="text-center mb-16">
            <h2 className="text-4xl sm:text-5xl font-display font-bold mb-6 text-white tracking-tight">
              Start a Conversation
            </h2>
            <p className="text-xl text-zinc-400">
              Have an expensive problem? Let&apos;s solve it together.
            </p>
          </div>
        </RevealOnScroll>

        <RevealOnScroll delay={0.2}>
          <SpotlightCard className="p-8 sm:p-12 shadow-2xl ring-1 ring-zinc-800 bg-zinc-950/80 backdrop-blur-sm">
            <form className="space-y-8" onSubmit={onSubmit}>
              <div className="grid md:grid-cols-2 gap-8">
                <InputField
                  label="Name"
                  id="name"
                  placeholder="John Doe"
                  required
                  value={form.name}
                  onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                />
                <InputField
                  label="Email"
                  id="email"
                  type="email"
                  placeholder="john@company.com"
                  required
                  value={form.email}
                  onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))}
                />
              </div>

              <InputField
                label="Company"
                id="company"
                placeholder="Acme Inc."
                value={form.company}
                onChange={(e) => setForm((prev) => ({ ...prev, company: e.target.value }))}
              />

              <div className="group">
                <label htmlFor="problem" className="mb-2 block text-sm font-medium text-zinc-400 transition-colors group-focus-within:text-blue-400">
                  What&apos;s the expensive problem?
                </label>
                <textarea
                  rows="5"
                  id="problem"
                  name="problem"
                  className="w-full resize-none rounded-xl border border-zinc-800 bg-zinc-900/50 px-4 py-3 text-zinc-100 placeholder:text-zinc-600 outline-none transition-all focus:border-blue-500/50 focus:bg-zinc-900 focus:ring-4 focus:ring-blue-500/10"
                  placeholder="We're spending $X on Y and it's killing us..."
                  required
                  value={form.problem}
                  onChange={(e) => setForm((prev) => ({ ...prev, problem: e.target.value }))}
                ></textarea>
              </div>

              <div className="group">
                <label htmlFor="timeline" className="mb-2 block text-sm font-medium text-zinc-400 transition-colors group-focus-within:text-blue-400">
                  Timeline
                </label>
                <div className="relative">
                  <select
                    id="timeline"
                    name="timeline"
                    className="w-full appearance-none rounded-xl border border-zinc-800 bg-zinc-900/50 px-4 py-3 text-zinc-100 outline-none transition-all focus:border-blue-500/50 focus:bg-zinc-900 focus:ring-4 focus:ring-blue-500/10"
                    value={form.timeline}
                    onChange={(e) => setForm((prev) => ({ ...prev, timeline: e.target.value }))}
                  >
                    {timelineOptions.map((opt) => (
                      <option key={opt} value={opt}>
                        {opt}
                      </option>
                    ))}
                  </select>
                  <div className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-zinc-500">
                    ▼
                  </div>
                </div>
              </div>

              {error ? (
                <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200 animate-fade-in">
                  {error}
                </div>
              ) : null}

              {success ? (
                <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-6 py-4 animate-fade-in">
                  <div className="flex items-center gap-3 text-emerald-200 font-medium">
                    <CheckCircle2 className="h-5 w-5" />
                    {success}
                  </div>
                  <a
                    href={CALCOM_URL}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-3 inline-flex items-center gap-2 rounded-lg bg-emerald-500/20 px-4 py-2 text-sm font-semibold text-emerald-100 transition hover:bg-emerald-500/30"
                  >
                    Book a call now →
                  </a>
                </div>
              ) : null}

              <button
                type="submit"
                disabled={loading}
                className="group relative w-full overflow-hidden rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-8 py-4 text-lg font-bold text-white transition-all hover:scale-[1.02] hover:shadow-xl hover:shadow-blue-500/20 disabled:opacity-70 disabled:cursor-not-allowed disabled:hover:scale-100"
              >
                <div className="absolute inset-0 bg-white/20 opacity-0 transition-opacity group-hover:opacity-100" />
                <span className="relative flex items-center justify-center gap-2">
                  {loading ? (
                    <>
                      <Loader2 className="h-5 w-5 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      Send Inquiry
                      <Send className="h-5 w-5 transition-transform group-hover:translate-x-1 group-hover:-translate-y-1" />
                    </>
                  )}
                </span>
              </button>
            </form>

            <div className="mt-12 pt-8 border-t border-zinc-800/50 text-center">
              <p className="text-zinc-500 mb-6 text-sm uppercase tracking-wider font-semibold">Or reach out directly</p>
              <div className="flex flex-wrap gap-4 justify-center">
                <a href={`mailto:${CONTACT_EMAIL}`} className="group flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/50 px-5 py-2.5 text-sm font-medium text-zinc-300 transition-all hover:border-zinc-700 hover:bg-zinc-800 hover:text-white">
                  <Mail className="h-4 w-4 text-zinc-500 group-hover:text-blue-400 transition-colors" />
                  {CONTACT_EMAIL}
                </a>
                <a
                  href={LINKEDIN_URL}
                  target="_blank"
                  rel="noreferrer"
                  className="group flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/50 px-5 py-2.5 text-sm font-medium text-zinc-300 transition-all hover:border-zinc-700 hover:bg-zinc-800 hover:text-white"
                >
                  <Linkedin className="h-4 w-4 text-zinc-500 group-hover:text-blue-400 transition-colors" />
                  LinkedIn
                </a>
                <a
                  href={GITHUB_URL}
                  target="_blank"
                  rel="noreferrer"
                  className="group flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/50 px-5 py-2.5 text-sm font-medium text-zinc-300 transition-all hover:border-zinc-700 hover:bg-zinc-800 hover:text-white"
                >
                  <Github className="h-4 w-4 text-zinc-500 group-hover:text-blue-400 transition-colors" />
                  GitHub
                </a>
              </div>
            </div>
          </SpotlightCard>
        </RevealOnScroll>

        <p className="mt-12 text-center text-xs text-zinc-600 max-w-2xl mx-auto">
          Magnio is built as a proof of automation, guardrails, and measurable outcomes. This is the same approach
          we deliver to clients.
        </p>

      </div>
    </section>
  );
}

export default ContactSection;
