import { Suspense, lazy, useEffect, useState } from 'react'

import AdminLeadsSection from './components/AdminLeadsSection'
import ContactSection from './components/ContactSection'
import HeroSection from './components/HeroSection'
import IntakeSection from './components/IntakeSection'
import Navigation from './components/Navigation'
import ServicesSection from './components/ServicesSection'

const ChatPage = lazy(() => import('./chat/ChatPage'))
const JobRadarPanel = lazy(() => import('./components/JobRadarPanel'))

type AppRoute = 'main' | 'admin' | 'chat' | 'intake' | 'jobs'

function resolveRoute(): AppRoute {
  const pathname = window.location.pathname.replace(/\/+$/, '') || '/'
  if (pathname === '/chat') return 'chat'
  if (pathname === '/jobs') return 'jobs'

  const hash = window.location.hash
  if (hash.startsWith('#admin')) return 'admin'
  if (hash.startsWith('#intake')) return 'intake'
  if (hash.startsWith('#jobs')) return 'jobs'
  return 'main'
}

function LandingPage() {
  return (
    <div className="min-h-screen">
      <Navigation />
      <HeroSection />
      <ServicesSection />
      <ContactSection />

      <footer className="border-t border-zinc-800/60 bg-zinc-950 py-10">
        <div className="magnio-container flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-sm text-zinc-500">
            © {new Date().getFullYear()} Magnio. Independent engineering services.
          </div>
          <div className="flex flex-wrap gap-6 text-sm">
            <a className="magnio-link" href="#services">
              Work
            </a>
            <a className="magnio-link" href="/chat">
              Chat
            </a>
            <a className="magnio-link" href="#contact">
              Contact
            </a>
            <a className="magnio-link" href="mailto:hello@magnio.io">
              Email
            </a>
            <a
              className="magnio-link"
              href="https://www.linkedin.com/in/sebastian-rosales-3a83a851/"
              rel="noreferrer"
              target="_blank"
            >
              LinkedIn
            </a>
            <a
              className="magnio-link"
              href="https://github.com/sebasrosalesr"
              rel="noreferrer"
              target="_blank"
            >
              GitHub
            </a>
          </div>
        </div>
      </footer>
    </div>
  )
}

function App() {
  const [route, setRoute] = useState<AppRoute>(() => resolveRoute())

  useEffect(() => {
    const update = () => setRoute(resolveRoute())
    update()
    window.addEventListener('hashchange', update)
    window.addEventListener('popstate', update)
    return () => {
      window.removeEventListener('hashchange', update)
      window.removeEventListener('popstate', update)
    }
  }, [])

  if (route === 'chat') {
    return (
      <Suspense
        fallback={
          <div className="flex min-h-screen items-center justify-center bg-[#060c14] text-slate-100">
            <div className="rounded-3xl border border-white/10 bg-white/[0.04] px-6 py-5 text-sm text-slate-300">
              Loading Magnio Chat...
            </div>
          </div>
        }
      >
        <ChatPage />
      </Suspense>
    )
  }

  if (route === 'intake') {
    return (
      <div className="min-h-screen">
        <IntakeSection />
      </div>
    )
  }

  if (route === 'admin') {
    return (
      <div className="min-h-screen">
        <AdminLeadsSection />
      </div>
    )
  }

  if (route === 'jobs') {
    return (
      <Suspense
        fallback={
          <div className="flex min-h-screen items-center justify-center bg-[#060c14] text-slate-100">
            <div className="rounded-3xl border border-white/10 bg-white/[0.04] px-6 py-5 text-sm text-slate-300">
              Loading JobRadar...
            </div>
          </div>
        }
      >
        <JobRadarPanel />
      </Suspense>
    )
  }

  return <LandingPage />
}

export default App
