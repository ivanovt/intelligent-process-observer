import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { ObservationDetailPage } from './features/observations/ObservationDetailPage'
import { ObservationsPage } from './features/observations/ObservationsPage'

/** Defines the currently supported frontend route tree. */
export default function App() {
  return <Routes><Route element={<AppShell />}><Route path="/observations" element={<ObservationsPage />} /><Route path="/observations/new" element={<CreateObservationSeam />} /><Route path="/observations/:observationId" element={<ObservationDetailPage />} /><Route path="/" element={<Navigate to="/observations" replace />} /><Route path="*" element={<Navigate to="/observations" replace />} /></Route></Routes>
}

/** Preserves the create-route seam until the approved draft slice supplies its content. */
function CreateObservationSeam() {
  return <section className="mx-auto max-w-6xl"><h1 className="text-[28px] font-semibold tracking-tight">Create Observation</h1><p className="mt-2 text-[var(--color-text-secondary)]">Observation configuration is available in the next delivery.</p></section>
}
