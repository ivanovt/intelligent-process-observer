import { Navigate, Outlet, Route, Routes, useParams } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { DataSourcesPage } from './features/data-sources/DataSourcesPage'
import { OverviewPage } from './features/overview/OverviewPage'
import { ObservationDetailPage } from './features/observations/ObservationDetailPage'
import { ObservationsPage } from './features/observations/ObservationsPage'
import { AlertLensEditorPage } from './features/observations/AlertLensEditorPage'
import { MetricLensEditorPage } from './features/observations/MetricLensEditorPage'
import { RelationshipEditorPage } from './features/observations/RelationshipEditorPage'
import { CreateObservationPage } from './features/observations/CreateObservationPage'
import { EditObservationPage } from './features/observations/EditObservationPage'
import { ObservationDraftProvider } from './features/observations/draft'
import { RunDetailPage } from './features/runs/RunDetailPage'
import { RunsPage } from './features/runs/RunsPage'

/** Defines the currently supported frontend route tree. */
export default function App() {
  return <Routes><Route element={<AppShell />}><Route path="/overview" element={<OverviewPage />} /><Route path="/observations" element={<ObservationsPage />} /><Route path="/observations/new" element={<CreateRoutes/>}><Route index element={<CreateObservationPage/>}/><Route path="alert-lenses/:key" element={<AlertLensEditorPage/>}/><Route path="metric-lenses/:key" element={<MetricLensEditorPage/>}/><Route path="relationships/:key" element={<RelationshipEditorPage/>}/></Route><Route path="/observations/:observationId/edit" element={<EditRoutes/>}><Route index element={<EditObservationPage/>}/><Route path="alert-lenses/:key" element={<AlertLensEditorPage/>}/><Route path="metric-lenses/:key" element={<MetricLensEditorPage/>}/><Route path="relationships/:key" element={<RelationshipEditorPage/>}/></Route><Route path="/observations/:observationId" element={<ObservationDetailPage />} /><Route path="/runs" element={<RunsPage />} /><Route path="/runs/:observationRunId" element={<RunDetailPage />} /><Route path="/data-sources" element={<DataSourcesPage />} /><Route path="/" element={<Navigate to="/overview" replace />} /><Route path="*" element={<Navigate to="/overview" replace />} /></Route></Routes>
}
function CreateRoutes(){return <ObservationDraftProvider><Outlet/></ObservationDraftProvider>}
function EditRoutes(){const {observationId=''}=useParams();return <ObservationDraftProvider mode="edit" targetId={observationId}><Outlet/></ObservationDraftProvider>}
