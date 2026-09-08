import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { ObservationDetailPage } from './features/observations/ObservationDetailPage'
import { ObservationsPage } from './features/observations/ObservationsPage'
import { AlertLensEditorPage } from './features/observations/AlertLensEditorPage'
import { MetricLensEditorPage } from './features/observations/MetricLensEditorPage'
import { RelationshipEditorPage } from './features/observations/RelationshipEditorPage'
import { CreateObservationPage } from './features/observations/CreateObservationPage'
import { ObservationDraftProvider } from './features/observations/draft'

/** Defines the currently supported frontend route tree. */
export default function App() {
  return <Routes><Route element={<AppShell />}><Route path="/observations" element={<ObservationsPage />} /><Route path="/observations/new" element={<CreateRoutes/>}><Route index element={<CreateObservationPage/>}/><Route path="alert-lenses/:key" element={<AlertLensEditorPage/>}/><Route path="metric-lenses/:key" element={<MetricLensEditorPage/>}/><Route path="relationships/:key" element={<RelationshipEditorPage/>}/></Route><Route path="/observations/:observationId" element={<ObservationDetailPage />} /><Route path="/" element={<Navigate to="/observations" replace />} /><Route path="*" element={<Navigate to="/observations" replace />} /></Route></Routes>
}
function CreateRoutes(){return <ObservationDraftProvider><Outlet/></ObservationDraftProvider>}
