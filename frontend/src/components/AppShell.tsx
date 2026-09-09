import { Activity, Database, FileText, LayoutDashboard, Settings, Telescope } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'

const navigation = [
  ['Overview', LayoutDashboard],
  ['Observations', Telescope],
  ['Runs', Activity],
  ['Reports', FileText],
  ['Data Sources', Database],
  ['Settings', Settings],
] as const

/** Renders the persistent ObserveAI product shell. */
export function AppShell() {
  return (
    <div className="min-h-screen bg-[var(--color-background-canvas)] text-[var(--color-text-primary)] lg:flex">
      <aside className="border-slate-800 bg-slate-950 px-4 py-5 text-slate-200 lg:min-h-screen lg:w-60 lg:border-r xl:w-64">
        <div className="mb-8 flex items-center gap-2.5 px-3 text-xl font-semibold tracking-tight text-white">
          <span className="flex size-8 items-center justify-center rounded-lg bg-blue-500/15 text-blue-300"><Activity size={20} strokeWidth={2.25} aria-hidden="true" /></span>
          <span>ObserveAI</span>
        </div>
        <nav aria-label="Main navigation" className="flex gap-1 overflow-x-auto pb-1 lg:block lg:space-y-1 lg:overflow-visible">
          {navigation.map(([label, Icon]) => label === 'Observations' || label === 'Data Sources' || label === 'Runs' ? (
            <NavLink
              key={label}
              to={label === 'Observations' ? '/observations' : label === 'Runs' ? '/runs' : '/data-sources'}
              className={({ isActive }) => `flex h-10 shrink-0 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors ${isActive ? 'bg-slate-800 text-white shadow-sm' : 'text-slate-400 hover:bg-slate-900 hover:text-white'}`}
            >
              <Icon size={17} strokeWidth={2} aria-hidden="true" />
              {label}
            </NavLink>
          ) : (
            <span key={label} className="flex h-10 shrink-0 items-center gap-3 rounded-lg px-3 text-sm font-medium text-slate-400">
              <Icon size={17} strokeWidth={2} aria-hidden="true" />
              {label}
            </span>
          ))}
        </nav>
      </aside>
      <main className="min-w-0 flex-1 px-5 py-8 sm:px-8 lg:px-10 lg:py-10"><Outlet /></main>
    </div>
  )
}
