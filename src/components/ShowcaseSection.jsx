const ShowcaseSection = () => {
  const highlights = [
    {
      title: "$481K incident → eliminated",
      subtitle: "Automation + guardrails + rollout plan",
      outcome: "Solved in 5 months, 1,721% ROI, $280K annual savings",
      tags: ["Automation", "Reliability", "Ops"],
    },
    {
      title: "MVP → production in weeks",
      subtitle: "Ship fast without painting yourself into a corner",
      outcome: "Clear scope, iterative delivery, deployment on day one",
      tags: ["Full‑stack", "Architecture", "Delivery"],
    },
    {
      title: "System audit + roadmap",
      subtitle: "Performance, scalability, security",
      outcome: "Bottlenecks found, risks prioritized, plan your team can execute",
      tags: ["Performance", "Security", "Scalability"],
    },
  ];

  return (
    <section id="work" className="magnio-section bg-zinc-950">
      <div className="magnio-container">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="text-4xl sm:text-5xl font-display font-bold tracking-tight text-white h2-gradient">
            Outcomes over output.
          </h2>
          <p className="mt-5 text-lg sm:text-xl text-zinc-400">
            A few examples of the kind of work I do and the results I optimize for.
          </p>
        </div>

        <div className="mt-14 grid gap-6 lg:grid-cols-3">
          {highlights.map((item) => (
            <div key={item.title} className="magnio-card magnio-card-hover p-7 group">
              <div className="text-sm font-semibold text-blue-400">{item.subtitle}</div>
              <div className="mt-3 text-2xl font-display font-bold text-white tracking-tight">{item.title}</div>
              <div className="mt-3 text-zinc-400 leading-relaxed">{item.outcome}</div>

              <div className="mt-6 flex flex-wrap gap-2">
                {item.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full border border-zinc-800 bg-zinc-900/60 px-3 py-1 text-xs font-semibold text-zinc-300"
                  >
                    {tag}
                  </span>
                ))}
              </div>

              <div className="mt-7">
                <a
                  href="#contact"
                  className="inline-flex w-full items-center justify-center rounded-xl border border-zinc-700 bg-zinc-800/50 px-5 py-3 font-semibold text-zinc-100 transition-all hover:bg-zinc-800 hover:border-zinc-600 hover:text-white"
                >
                  Talk through a similar challenge →
                </a>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-10 text-center text-sm text-zinc-500">
          Want the details? I can share a sanitized walkthrough on a call.
        </div>
      </div>
    </section>
  );
};

export default ShowcaseSection;
