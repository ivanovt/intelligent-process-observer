import { Database, RefreshCw, Server } from 'lucide-react'
import { Button, InlineNotice, PageHeader } from '../../components/ui'
import { getDefinitionCapabilities } from '../observations/api'
import { useRequest } from '../observations/useRequest'

/** Lists the server-managed Metric sources safely projected by the capabilities API. */
export function DataSourcesPage() {
  const { state, retry } = useRequest(getDefinitionCapabilities, [])
  const sources = state.status === 'success'
    ? state.data.metric.flatMap((adapter) => adapter.sources.map((source) => ({ ...source, adapterType: adapter.adapter_type })))
    : []

  return (
    <section className="mx-auto max-w-6xl">
      <PageHeader
        eyebrow="Environment-managed configuration"
        title="Data Sources"
        description="Metric sources are configured in the backend environment and are available to Metric Lens configuration."
        actions={<Button variant="secondary" type="button" onClick={retry}><RefreshCw size={17} aria-hidden="true" />Refresh sources</Button>}
      />

      {state.status === 'loading' ? <StatePanel title="Loading Metric sources" detail="Retrieving the configured sources from the running backend…" /> : null}
      {state.status === 'error' ? (
        <InlineNotice tone="error">
          Unable to load Metric sources. <button className="font-semibold underline underline-offset-2" type="button" onClick={retry}>Retry</button>
        </InlineNotice>
      ) : null}
      {state.status === 'success' && sources.length === 0 ? <EmptySources /> : null}
      {state.status === 'success' && sources.length > 0 ? <ConfiguredSources sources={sources} /> : null}
    </section>
  )
}

/** Displays safely projected configured Metric sources in backend-provided order. */
function ConfiguredSources({ sources }: { sources: Array<{ id: string; name: string; adapterType: 'prometheus' }> }) {
  return (
    <div className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-xs">
      <div className="border-b border-[var(--color-border)] bg-[var(--color-surface-muted)] px-5 py-4">
        <h2 className="font-semibold">Configured Metric sources</h2>
        <p className="mt-1 text-sm text-[var(--color-text-secondary)]">These sources are available when configuring a Metric Lens.</p>
      </div>
      <ul aria-label="Configured Metric sources" className="divide-y divide-[var(--color-border)]">
        {sources.map((source) => (
          <li key={source.id} className="flex flex-col gap-4 px-5 py-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex min-w-0 items-start gap-3">
              <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-blue-500/10 text-[var(--color-primary)]"><Server size={18} aria-hidden="true" /></span>
              <div className="min-w-0">
                <h3 className="break-words font-semibold">{source.name}</h3>
                <p className="mt-1 break-all font-mono text-xs text-[var(--color-text-secondary)]">{source.id}</p>
              </div>
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-2 text-sm">
              <span className="rounded-full bg-[var(--color-surface-muted)] px-2.5 py-1 font-medium text-[var(--color-text-secondary)]">Prometheus</span>
              <span className="text-[var(--color-success)]">Available for Metric Lens</span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Explains the environment-only source configuration path when no source is available. */
function EmptySources() {
  return (
    <div className="space-y-5">
      <StatePanel title="No Metric sources are configured" detail="Add one or more Prometheus sources to the backend environment, then restart the backend and refresh this page." />
      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xs">
        <div className="flex items-start gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-blue-500/10 text-[var(--color-primary)]"><Database size={18} aria-hidden="true" /></span>
          <div>
            <h2 className="font-semibold">Configure <code className="font-mono text-sm">PROMETHEUS_SOURCES</code> in the backend environment</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">Use the root backend <code className="font-mono text-xs">.env</code> for local development or your deployment environment. The value is a JSON array, so multiple Prometheus systems are supported. Each entry needs a unique stable ID, display name, base URL, and exactly one credential shape.</p>
          </div>
        </div>

        <div className="mt-5 grid gap-4 xl:grid-cols-2">
          <Example title="Bearer token (placeholder only)" value={'PROMETHEUS_SOURCES=[\n  {\n    "id": "primary",\n    "name": "Primary metrics",\n    "base_url": "https://prometheus.example.invalid",\n    "credentials": {\n      "type": "bearer_token",\n      "token": "replace-with-a-real-secret"\n    }\n  }\n]'} />
          <Example title="Basic authentication (placeholder only)" value={'PROMETHEUS_SOURCES=[\n  {\n    "id": "secondary",\n    "name": "Secondary metrics",\n    "base_url": "https://secondary.example.invalid",\n    "credentials": {\n      "type": "basic_auth",\n      "username": "replace-with-a-real-username",\n      "password": "replace-with-a-real-secret"\n    }\n  }\n]'} />
        </div>

        <ol className="mt-5 list-decimal space-y-1.5 pl-5 text-sm leading-6 text-[var(--color-text-secondary)]">
          <li>Set <code className="font-mono text-xs">PROMETHEUS_SOURCES</code> in the root backend or deployment environment.</li>
          <li>Restart the backend so it loads the updated environment configuration.</li>
          <li>Select <strong className="font-medium text-[var(--color-text-primary)]">Refresh sources</strong> above to re-read the running backend.</li>
        </ol>
        <div className="mt-5"><InlineNotice tone="warning">Examples are non-production placeholders. Keep real credentials only in local or deployment environment configuration—never commit them, place them in frontend files, or use <code className="font-mono text-xs">VITE_*</code> variables.</InlineNotice></div>
      </div>
    </div>
  )
}

/** Renders a static, non-submittable environment configuration example. */
function Example({ title, value }: { title: string; value: string }) {
  return <div className="overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)]"><h3 className="border-b border-[var(--color-border)] px-4 py-3 text-sm font-semibold">{title}</h3><pre className="overflow-x-auto p-4 text-xs leading-5 text-[var(--color-text-secondary)]"><code>{value}</code></pre></div>
}

/** Renders a contained asynchronous page state. */
function StatePanel({ title, detail }: { title: string; detail: string }) {
  return <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-6 py-10 text-center shadow-xs"><h2 className="font-semibold">{title}</h2><p className="mx-auto mt-2 max-w-xl text-sm text-[var(--color-text-secondary)]">{detail}</p></div>
}
