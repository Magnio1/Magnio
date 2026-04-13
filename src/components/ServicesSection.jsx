import { useState } from "react";
import { Database, Bot, Globe, Settings2, ChevronDown, ArrowRight, Sparkles, Radar, NotebookTabs } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import SpotlightCard from "./SpotlightCard";
import RevealOnScroll from "./RevealOnScroll";

const servicesList = [
  {
    icon: <Database className="h-6 w-6 text-blue-400" />,
    title: "Custom CRM & Workflow Systems",
    description: (
      <ul className="space-y-1 mt-2">
        <li className="flex items-start gap-2"><span className="text-blue-400">✓</span> Design CRM systems around your real workflow — not generic templates</li>
        <li className="flex items-start gap-2"><span className="text-blue-400">✓</span> Align data capture with how your team actually operates</li>
        <li className="flex items-start gap-2"><span className="text-blue-400">✓</span> Build structured tracking for tickets, credits, approvals, and status</li>
        <li className="flex items-start gap-2"><span className="text-blue-400">✓</span> Connect CRM with automation to reduce manual entry</li>
        <li className="flex items-start gap-2"><span className="text-blue-400">✓</span> Improve visibility across teams with real-time dashboards</li>
        <li className="flex items-start gap-2"><span className="text-blue-400">✓</span> Ensure clean, reliable data for better decisions</li>
        <li className="flex items-start gap-2"><span className="text-blue-400">✓</span> Create role-based access for secure collaboration</li>
        <li className="flex items-start gap-2"><span className="text-blue-400">✓</span> Track performance, trends, and operational bottlenecks</li>
        <li className="flex items-start gap-2"><span className="text-blue-400">✓</span> Continuously refine processes based on real usage</li>
      </ul>
    )
  },
  {
    icon: <Bot className="h-6 w-6 text-purple-400" />,
    title: "Agentic AI & Intelligent Automation",
    description: (
      <ul className="space-y-1 mt-2">
        <li className="flex items-start gap-2"><span className="text-purple-400">✓</span> Turn repetitive work into intelligent workflows</li>
        <li className="flex items-start gap-2"><span className="text-purple-400">✓</span> Connect systems so information flows automatically</li>
        <li className="flex items-start gap-2"><span className="text-purple-400">✓</span> Reduce manual effort with smart decision support</li>
        <li className="flex items-start gap-2"><span className="text-purple-400">✓</span> Standardize processes across teams</li>
        <li className="flex items-start gap-2"><span className="text-purple-400">✓</span> Improve speed, accuracy, and visibility</li>
        <li className="flex items-start gap-2"><span className="text-purple-400">✓</span> Keep AI systems reliable and aligned with business goals</li>
        <li className="flex items-start gap-2"><span className="text-purple-400">✓</span> Train teams to confidently use AI tools</li>
        <li className="flex items-start gap-2"><span className="text-purple-400">✓</span> Build scalable solutions that grow with the organization</li>
        <li className="flex items-start gap-2"><span className="text-purple-400">✓</span> Continuously optimize based on real data</li>
      </ul>
    )
  },
  {
    icon: <Globe className="h-6 w-6 text-emerald-400" />,
    title: "Web Portal Automation",
    description: (
      <ul className="space-y-1 mt-2">
        <li className="flex items-start gap-2"><span className="text-emerald-400">✓</span> Create self-service portals that eliminate manual data entry</li>
        <li className="flex items-start gap-2"><span className="text-emerald-400">✓</span> Allow customers and teams to submit requests directly</li>
        <li className="flex items-start gap-2"><span className="text-emerald-400">✓</span> Automatically route submissions to the right workflow</li>
        <li className="flex items-start gap-2"><span className="text-emerald-400">✓</span> Validate data at the source to reduce errors</li>
        <li className="flex items-start gap-2"><span className="text-emerald-400">✓</span> Reduce email back-and-forth and spreadsheet chaos</li>
        <li className="flex items-start gap-2"><span className="text-emerald-400">✓</span> Track submissions in real time with status visibility</li>
        <li className="flex items-start gap-2"><span className="text-emerald-400">✓</span> Connect portal activity to internal systems seamlessly</li>
        <li className="flex items-start gap-2"><span className="text-emerald-400">✓</span> Improve response time and operational efficiency</li>
        <li className="flex items-start gap-2"><span className="text-emerald-400">✓</span> Scale operations without increasing headcount</li>
      </ul>
    )
  },
  {
    icon: <Settings2 className="h-6 w-6 text-pink-400" />,
    title: "Internal Process Improvement",
    description: (
      <ul className="space-y-1 mt-2">
        <li className="flex items-start gap-2"><span className="text-pink-400">✓</span> Assess. Design. Solve.</li>
        <li className="flex items-start gap-2"><span className="text-pink-400">✓</span> Fix systems. Add automation.</li>
        <li className="flex items-start gap-2"><span className="text-pink-400">✓</span> Keep processes running smoothly.</li>
        <li className="flex items-start gap-2"><span className="text-pink-400">✓</span> Train teams. Share knowledge.</li>
        <li className="flex items-start gap-2"><span className="text-pink-400">✓</span> Set up continuous improvement.</li>
      </ul>
    )
  }
];

const ServiceAccordionItem = ({ icon, title, description, delay }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <RevealOnScroll delay={delay}>
      <div
        onClick={() => setIsOpen(!isOpen)}
        className={`group cursor-pointer rounded-2xl border bg-zinc-900/20 p-6 transition-colors hover:bg-zinc-900/40 hover:shadow-lg hover:shadow-blue-900/5 ${isOpen ? "border-blue-500/30 ring-1 ring-blue-500/20" : "border-zinc-800/50 hover:border-zinc-700/80"
          }`}
      >
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className={`shrink-0 rounded-lg p-3 ring-1 transition-all ${isOpen ? "bg-blue-500/10 ring-blue-500/30" : "bg-zinc-950 ring-zinc-800 group-hover:ring-zinc-700"
              }`}>
              {icon}
            </div>
            <h3 className={`font-display font-bold text-lg transition-colors ${isOpen ? "text-blue-400" : "text-zinc-100 group-hover:text-blue-200"
              }`}>
              {title}
            </h3>
          </div>
          <ChevronDown className={`h-5 w-5 shrink-0 text-zinc-500 transition-transform duration-200 ${isOpen ? "rotate-180 text-blue-400" : ""}`} />
        </div>

        <AnimatePresence initial={false}>
          {isOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
              className="overflow-hidden"
            >
              <div className="pt-4 pl-[3.25rem]">
                <div className="text-sm text-zinc-400 leading-relaxed">
                  {description}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </RevealOnScroll>
  );
};

function ServicesSection() {
  return (
    <section id="services" className="magnio-section relative overflow-hidden">
      {/* Background glow effects */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden [mask-image:linear-gradient(to_bottom,transparent,black_10%,black_90%,transparent)]">
        <div className="absolute top-0 right-0 -mr-40 -mt-40 h-96 w-96 rounded-full bg-blue-500/5 blur-[100px]" />
        <div className="absolute bottom-0 left-0 -ml-40 -mb-40 h-96 w-96 rounded-full bg-purple-500/5 blur-[100px]" />
      </div>

      <div className="magnio-container relative">

        <RevealOnScroll>
          <div className="text-center mb-12">
            <h2 className="text-4xl sm:text-5xl font-display font-bold mb-6 tracking-tight">
              <span className="magnio-gradient-text">See Magnio</span>
              <span className="text-white"> In Action</span>
            </h2>
            <p className="text-lg sm:text-xl text-zinc-400 max-w-3xl mx-auto leading-relaxed">
              Start with the live agentic system, then explore the automation services below.
            </p>
          </div>
        </RevealOnScroll>

        <RevealOnScroll delay={0.2}>
          <div className="mx-auto max-w-4xl">
            <SpotlightCard className="w-full overflow-hidden rounded-[2rem] bg-zinc-950 shadow-2xl ring-1 ring-zinc-800">
              <div className="grid gap-8 bg-[radial-gradient(circle_at_top_left,rgba(6,182,212,0.12),transparent_38%),radial-gradient(circle_at_bottom_right,rgba(245,158,11,0.12),transparent_36%)] p-8 sm:p-10 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
                <div className="space-y-6">
                  <div className="inline-flex items-center gap-2 rounded-full border border-cyan-500/25 bg-cyan-500/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.32em] text-cyan-200">
                    <Sparkles className="h-4 w-4" />
                    Live Agentic Demo
                  </div>
                  <div className="space-y-4">
                    <h3 className="max-w-2xl text-3xl font-display font-bold tracking-tight text-white sm:text-4xl">
                      Test the live chat system before you look at the service stack.
                    </h3>
                    <p className="max-w-2xl text-base leading-8 text-zinc-400 sm:text-lg">
                      Run the arena, inspect routed model decisions, and try the grounded advisor. This is the live proof layer behind Magnio's automation and small-business AI systems.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <a
                      href="/chat"
                      className="inline-flex items-center gap-2 rounded-full bg-cyan-400 px-6 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-300"
                    >
                      Open /chat
                      <ArrowRight className="h-4 w-4" />
                    </a>
                    <a
                      href="/chat"
                      className="inline-flex items-center gap-2 rounded-full border border-zinc-700 bg-zinc-950/60 px-6 py-3 text-sm font-semibold text-zinc-200 transition hover:border-zinc-500 hover:text-white"
                    >
                      Run a live prompt
                    </a>
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
                  <div className="rounded-3xl border border-cyan-500/20 bg-zinc-950/70 p-5">
                    <div className="mb-3 inline-flex rounded-2xl border border-cyan-500/20 bg-cyan-500/10 p-3 text-cyan-200">
                      <Radar className="h-5 w-5" />
                    </div>
                    <p className="text-xs font-semibold uppercase tracking-[0.28em] text-zinc-500">Arena</p>
                    <p className="mt-2 text-sm leading-7 text-zinc-300">
                      Ranked multi-model orchestration with a judge layer and a final synthesis.
                    </p>
                  </div>
                  <div className="rounded-3xl border border-amber-500/20 bg-zinc-950/70 p-5">
                    <div className="mb-3 inline-flex rounded-2xl border border-amber-500/20 bg-amber-500/10 p-3 text-amber-200">
                      <NotebookTabs className="h-5 w-5" />
                    </div>
                    <p className="text-xs font-semibold uppercase tracking-[0.28em] text-zinc-500">Advisor</p>
                    <p className="mt-2 text-sm leading-7 text-zinc-300">
                      Retrieval-backed guidance grounded in Magnio positioning, delivery, and practical rollout advice.
                    </p>
                  </div>
                  <div className="rounded-3xl border border-emerald-500/20 bg-zinc-950/70 p-5">
                    <div className="mb-3 inline-flex rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-3 text-emerald-200">
                      <Bot className="h-5 w-5" />
                    </div>
                    <p className="text-xs font-semibold uppercase tracking-[0.28em] text-zinc-500">Review Loop</p>
                    <p className="mt-2 text-sm leading-7 text-zinc-300">
                      Persist evaluation cases, operator reviews, and rollups directly in Firestore.
                    </p>
                  </div>
                </div>
              </div>
            </SpotlightCard>
            <h3 className="text-white font-bold tracking-wide text-3xl mt-16 text-center">Automation Services</h3>
          </div>
        </RevealOnScroll>

        <div className="mx-auto max-w-5xl mt-16">
          <div className="grid md:grid-cols-2 gap-6">
            {servicesList.map((service, index) => (
              <ServiceAccordionItem
                key={index}
                {...service}
                delay={0.3 + (index * 0.1)}
              />
            ))}
          </div>
        </div>

      </div>
    </section>
  );
}

export default ServicesSection;
