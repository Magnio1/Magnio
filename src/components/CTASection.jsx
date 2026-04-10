const CTASection = () => {
  return (
    <section className="magnio-section">
      <div className="magnio-container">
        <div className="magnio-card p-8 sm:p-12 relative overflow-hidden">
          <div className="absolute top-0 right-0 -mr-20 -mt-20 h-64 w-64 rounded-full bg-blue-500/10 blur-3xl" />
          <div className="grid gap-8 lg:grid-cols-[1.2fr,0.8fr] lg:items-center relative">
            <div>
              <h2 className="text-3xl sm:text-4xl font-display font-bold tracking-tight text-white mb-6">
                If it’s expensive, urgent, and technical it’s my lane.
              </h2>
              <p className="mt-4 text-lg text-zinc-400 leading-relaxed">
                Bring the constraint. I’ll bring the plan, the build, and the deployment.
              </p>

              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <a href="#contact" className="inline-flex items-center justify-center rounded-xl bg-blue-600 px-6 py-4 font-bold text-white transition-all hover:bg-blue-500 hover:ring-2 hover:ring-blue-500/50 hover:ring-offset-2 hover:ring-offset-zinc-950">
                  Get an estimate →
                </a>
                <a
                  href="#services"
                  className="rounded-xl border border-zinc-700 bg-zinc-800/50 px-6 py-4 text-center font-semibold text-zinc-100 hover:bg-zinc-800 transition-colors"
                >
                  Compare services
                </a>
              </div>
            </div>

            <div className="grid gap-3">
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
                <div className="text-sm font-semibold text-zinc-200">Typical engagement</div>
                <div className="mt-2 text-2xl font-display font-bold magnio-gradient-text">2–6 weeks</div>
                <div className="mt-1 text-sm text-zinc-400">From discovery to shipped improvements</div>
              </div>
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
                <div className="text-sm font-semibold text-zinc-200">Communication</div>
                <div className="mt-2 text-lg font-bold text-white">Async-first</div>
                <div className="mt-1 text-sm text-zinc-400">Clear updates, decisive next steps</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default CTASection;
