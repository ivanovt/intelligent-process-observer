import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { ObservationDetailPage } from './features/observations/ObservationDetailPage'
import { ObservationsPage } from './features/observations/ObservationsPage'

/** Defines the currently supported frontend route tree. */
export default function App() {
  return <Routes><Route element={<AppShell />}><Route path="/observations" element={<ObservationsPage />} /><Route path="/observations/:observationId" element={<ObservationDetailPage />} /><Route path="/" element={<Navigate to="/observations" replace />} /><Route path="*" element={<Navigate to="/observations" replace />} /></Route></Routes>
}
