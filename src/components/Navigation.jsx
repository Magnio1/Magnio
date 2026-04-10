import MagnioLogo from "./MagnioLogo";

const CALCOM_URL = "https://cal.com/sebastian-rosales-iuyl0n/30min";

const Navigation = () => {
  return (
    <header className="sticky top-0 z-50 border-b border-zinc-800/80 bg-zinc-950/70 backdrop-blur-xl">
      <div className="magnio-container">
        <div className="flex h-16 items-center justify-between">
          <a href="#top" className="inline-flex items-center">
            <MagnioLogo size="small" />
          </a>

          <nav className="hidden items-center gap-8 sm:flex">
            <a href="/chat" className="text-sm font-semibold text-zinc-300 hover:text-white transition-colors">
              Chat
            </a>
            <a href="#services" className="text-sm font-semibold text-zinc-300 hover:text-white transition-colors">
              Work
            </a>
            <a href="#contact" className="text-sm font-semibold text-zinc-300 hover:text-white transition-colors">
              Contact
            </a>
          </nav>

          <div className="flex items-center gap-3">
            <a
              href={CALCOM_URL}
              target="_blank"
              rel="noreferrer"
              className="hidden rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-all hover:scale-105 hover:shadow-lg hover:shadow-blue-500/20 sm:inline-flex"
            >
              Book a call
            </a>
            <a
              href="#contact"
              className="inline-flex items-center justify-center rounded-lg border border-zinc-700 bg-zinc-800/50 px-4 py-2 text-sm font-semibold text-zinc-100 transition-colors hover:bg-zinc-800"
            >
              Start now
            </a>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Navigation;
