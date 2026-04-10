const TechnicalSection = () => {
  const approach = [
    {
      title: "Product & application systems",
      items: ["React, TypeScript", "Node.js, Python", "Firebase, SQLite", "Secure APIs & internal tools"],
    },
    {
      title: "Automation & intelligence",
      items: ["Workflow automation", "Hugging Face models", "TensorFlow where justified", "LLM integration with guardrails"],
    },
    {
      title: "Delivery & reliability",
      items: [
        "CI/CD pipelines",
        "Observability-first builds",
        "Fail-safe deployments",
        "Operational simplicity over complexity",
      ],
    },
  ];

  const tools = [
    "React",
    "TypeScript",
    "Node.js",
    "Python",
    "Firebase",
    "SQLite",
    "Hugging Face",
    "TensorFlow",
    "CI/CD",
    "Observability",
  ];

  return (
    <section id="technical" className="magnio-section bg-zinc-950 relative">
      <div className="magnio-container">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="text-4xl sm:text-5xl font-display font-bold tracking-tight text-white">
            Technical breadth, pragmatic depth.
          </h2>
          <p className="mt-5 text-lg sm:text-xl text-zinc-400 leading-relaxed">
            You get senior engineering judgment clear tradeoffs, fast decisions, and systems that hold up under
            pressure.
          </p>
        </div>

        <div className="mt-14 magnio-card p-7">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="text-sm font-semibold text-zinc-200">Engineering approach</div>
              <div className="mt-1 text-sm text-zinc-400">Depth where it matters. Simplicity where it doesn’t.</div>
            </div>
            <a href="#contact" className="inline-flex items-center justify-center rounded-lg border border-zinc-700 bg-zinc-800/50 px-4 py-2 text-sm font-semibold text-zinc-100 hover:bg-zinc-800 transition-colors">
              Talk through your problem →
            </a>
          </div>

          <div className="mt-8 grid gap-6 lg:grid-cols-3">
            {approach.map((group) => (
              <div
                key={group.title}
                className="rounded-2xl border border-zinc-800 bg-zinc-950/30 p-7 backdrop-blur-sm"
              >
                <div className="text-sm font-semibold text-zinc-200">{group.title}</div>
                <div className="mt-5 space-y-3">
                  {group.items.map((item) => (
                    <div key={item} className="flex items-start gap-3 text-zinc-400">
                      <span className="mt-1 text-emerald-400">✓</span>
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-8 border-t border-zinc-800 pt-6">
            <div className="text-sm font-semibold text-zinc-200">Tools I commonly use</div>
            <div className="mt-4 flex flex-wrap gap-2">
              {tools.map((tool) => (
                <span
                  key={tool}
                  className="rounded-full border border-zinc-800 bg-zinc-900/40 px-3 py-1 text-xs font-semibold text-zinc-300"
                >
                  {tool}
                </span>
              ))}
            </div>
          </div>
        </div>

        <p className="mt-8 text-center text-sm text-zinc-500 max-w-lg mx-auto">
          Magnio is built as a proof of automation, guardrails, and measurable outcomes. This is the same approach we
          deliver to clients.
        </p>
      </div>
    </section>
  );
};

export default TechnicalSection;
