import MagnioLogo from "./MagnioLogo";
import SpotlightCard from "./SpotlightCard";
import RevealOnScroll from "./RevealOnScroll";

const HeroSection = () => {
  return (
    <section id="top" className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-24 left-1/2 h-80 w-[38rem] -translate-x-1/2 rounded-full bg-blue-500/10 blur-3xl" />
        <div className="absolute top-40 -left-40 h-72 w-72 rounded-full bg-purple-500/10 blur-3xl" />
        <div className="absolute bottom-10 -right-40 h-72 w-72 rounded-full bg-pink-500/10 blur-3xl" />
      </div>

      <div className="magnio-container magnio-section relative">
        <div className="mx-auto max-w-3xl text-center">
          <RevealOnScroll>
            <div className="flex justify-center">
              <MagnioLogo size="large" className="justify-center" />
            </div>



            <h1 className="mt-8 text-balance font-display text-5xl font-bold tracking-tight text-white sm:text-7xl drop-shadow-sm">
              Build the right thing <span className="text-blue-400">fast</span> that <span className="text-purple-400">lasts</span>.
            </h1>

            <p className="mt-8 text-pretty text-lg text-zinc-400 sm:text-xl leading-relaxed">
              Independent engineers focused on automation, rapid builds, and production-ready systems.
            </p>

            <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <a href="#contact" className="group relative inline-flex h-12 items-center justify-center gap-2 overflow-hidden rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-8 font-medium text-white transition-all hover:scale-[1.02] hover:shadow-xl hover:shadow-blue-500/20 w-full sm:w-auto">
                <span>Start a conversation</span>
                <span className="transition-transform group-hover:translate-x-0.5">→</span>
              </a>
              <a
                href="#services"
                className="inline-flex h-12 w-full items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900/40 px-8 font-medium text-zinc-300 transition-all hover:bg-zinc-800 hover:text-white sm:w-auto"
              >
                See services
              </a>
            </div>
          </RevealOnScroll>

          <div className="mt-16 grid gap-4 sm:grid-cols-3">
            <RevealOnScroll delay={0.2} className="h-full">
              <SpotlightCard className="p-6 text-left relative overflow-hidden group h-full">
                <div className="absolute top-0 right-0 -mr-3 -mt-3 h-24 w-24 rounded-full bg-blue-500/10 blur-2xl transition-all group-hover:bg-blue-500/20" />
                <div className="text-sm font-semibold text-zinc-400">Recent impact</div>
                <div className="mt-3 text-2xl font-display font-semibold text-white tracking-tight text-balance leading-snug">
                  <span className="text-blue-200">$481K</span> loss prevented
                </div>
                <div className="mt-2 text-sm text-zinc-500">Fixed in five months.</div>
              </SpotlightCard>
            </RevealOnScroll>

            <RevealOnScroll delay={0.3} className="h-full">
              <SpotlightCard className="p-6 text-left relative overflow-hidden group h-full">
                <div className="absolute top-0 right-0 -mr-3 -mt-3 h-24 w-24 rounded-full bg-purple-500/10 blur-2xl transition-all group-hover:bg-purple-500/20" />
                <div className="text-sm font-semibold text-zinc-400">ROI delivered</div>
                <div className="mt-3 text-2xl font-display font-semibold text-white tracking-tight text-balance leading-snug">
                  <span className="text-purple-200">1,721%</span> ROI.
                </div>
                <div className="mt-2 text-sm text-zinc-500">Measured business outcome</div>
              </SpotlightCard>
            </RevealOnScroll>

            <RevealOnScroll delay={0.4} className="h-full">
              <SpotlightCard className="p-6 text-left relative overflow-hidden group h-full">
                <div className="absolute top-0 right-0 -mr-3 -mt-3 h-24 w-24 rounded-full bg-emerald-500/10 blur-2xl transition-all group-hover:bg-emerald-500/20" />
                <div className="text-sm font-semibold text-zinc-400">Savings</div>
                <div className="mt-3 text-2xl font-display font-semibold text-white tracking-tight text-balance leading-snug">
                  <span className="text-emerald-200">$280K</span> saved each year.
                </div>
                <div className="mt-2 text-sm text-zinc-500">Recurring cost reduction</div>
              </SpotlightCard>
            </RevealOnScroll>
          </div>


        </div>
      </div>
    </section>
  );
};

export default HeroSection;
