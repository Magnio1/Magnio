import SpotlightCard from "./SpotlightCard";
import RevealOnScroll from "./RevealOnScroll";

const StorySection = () => {
  const principles = [
    {
      title: "Start with the constraint",
      description:
        "Cost, time, risk, and the real user problem come first. From there, we work backward to the simplest viable build.",
    },
    {
      title: "Ship the first improvement fast",
      description: "De-risk early with something deployable. Then iterate with measurable feedback.",
    },
    {
      title: "Leave the team stronger",
      description:
        "Clear documentation, handoff, and training so your team is not dependent on me long term.",
    },
  ];

  return (
    <section id="story" className="magnio-section bg-zinc-900/10 relative">
      {/* Ambient background */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-zinc-900/50 to-transparent pointer-events-none" />

      <div className="magnio-container relative">
        <div className="grid gap-10 lg:grid-cols-2 lg:items-start">
          <RevealOnScroll>
            <div>
              <h2 className="text-4xl sm:text-5xl font-display font-bold tracking-tight text-white">
                Senior execution, founder-level urgency.
              </h2>
              <p className="mt-6 text-lg text-zinc-400 leading-relaxed">
                I work with teams that need decisive engineering leadership without adding headcount.
              </p>
              <p className="mt-4 text-lg text-zinc-400 leading-relaxed">
                When the stakes are high, including outages, cost overruns, brittle systems, or missed deadlines, I help
                you stabilize, simplify, and ship.
              </p>
              <p className="mt-4 text-lg text-zinc-400 leading-relaxed">
                The goal is not just code. The goal is a system your team can operate confidently.
              </p>

              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <a href="#contact" className="rounded-xl bg-white px-6 py-4 text-center font-bold text-zinc-900 transition-transform hover:scale-105">
                  Tell me the problem →
                </a>
                <a
                  href="#work"
                  className="rounded-xl border border-zinc-700 bg-zinc-800/50 px-6 py-4 text-center font-semibold text-zinc-100 hover:bg-zinc-800 transition-colors"
                >
                  See outcomes
                </a>
              </div>
            </div>
          </RevealOnScroll>

          <div className="grid gap-4">
            {principles.map((p, index) => (
              <RevealOnScroll key={p.title} delay={index * 0.1}>
                <SpotlightCard className="p-7">
                  <div className="text-lg font-display font-bold text-white">{p.title}</div>
                  <div className="mt-2 text-zinc-400">{p.description}</div>
                </SpotlightCard>
              </RevealOnScroll>
            ))}

            <RevealOnScroll delay={0.3}>
              <div className="rounded-2xl border border-zinc-700/50 bg-gradient-to-br from-zinc-900 to-zinc-950 p-7">
                <div className="text-sm font-semibold text-zinc-200">How we work</div>
                <div className="mt-3 grid gap-3 text-sm text-zinc-400">
                  <div className="flex items-start gap-3">
                    <span className="magnio-kbd">1</span>
                    <div>30-minute discovery to align on the constraint + success metric.</div>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="magnio-kbd">2</span>
                    <div>Short plan with scope, timeline, and risk callouts.</div>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="magnio-kbd">3</span>
                    <div>Build + deploy with tight feedback loops and weekly outcomes.</div>
                  </div>
                </div>
              </div>
            </RevealOnScroll>
          </div>
        </div>
      </div>
    </section>
  );
};

export default StorySection;
