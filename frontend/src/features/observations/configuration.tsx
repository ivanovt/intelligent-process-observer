import { CircleAlert, Plus, X } from 'lucide-react'
import { Button, Input } from '../../components/ui'

/** Edits an ordered, duplicate-free free-text list locally. */
export function AnalysisObjectivesField({ values, onChange, error }: { values: string[]; onChange: (values: string[]) => void; error?: string }) {
  const guidanceId = 'analysis-objectives-guidance'
  const errorId = 'analysis-objectives-error'
  const describedBy = error ? `${guidanceId} ${errorId}` : guidanceId

  return (
    <section id="analysis-objectives">
      <h3 className="font-semibold">Analysis objectives</h3>
      <p id={guidanceId} className="mt-1 text-sm text-[var(--color-text-secondary)]">
        Add concise analytical intents in the order they should guide analysis. Objectives do not select tools.
      </p>
      <div className="mt-3 space-y-2">
        {values.map((value, index) => (
          <div className="flex gap-2" key={index}>
            <Input
              aria-describedby={describedBy}
              aria-invalid={Boolean(error)}
              aria-label={`Objective ${index + 1}`}
              placeholder={index === 0 ? 'Assess recurrence' : 'Compare with reference periods'}
              value={value}
              onChange={(event) => onChange(values.map((item, itemIndex) => (itemIndex === index ? event.target.value : item)))}
            />
            <Button type="button" variant="ghost" aria-label={`Remove objective ${index + 1}`} onClick={() => onChange(values.filter((_, itemIndex) => itemIndex !== index))}>
              <X size={16} />
            </Button>
          </div>
        ))}
      </div>
      <button type="button" className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-[var(--color-primary)]" onClick={() => onChange([...values, ''])}>
        <Plus size={16} />
        Add objective
      </button>
      {error ? <p id={errorId} className="mt-1 flex items-center gap-1 text-sm text-[var(--color-error)]"><CircleAlert size={15} aria-hidden="true" />{error}</p> : null}
    </section>
  )
}

/** Edits ordered reference offsets locally. */
export function ReferencePeriodsField({ values, onChange, error }: { values: string[]; onChange: (values: string[]) => void; error?: string }) {
  const guidanceId = 'reference-periods-guidance'
  const errorId = 'reference-periods-error'
  const describedBy = error ? `${guidanceId} ${errorId}` : guidanceId

  return (
    <section id="reference-periods">
      <h3 className="font-semibold">Reference periods</h3>
      <p id={guidanceId} className="mt-1 text-sm text-[var(--color-text-secondary)]">
        Optionally compare an equal-duration earlier window using a unique positive offset such as 1d, 7d, or 14d.
      </p>
      <div className="mt-3 space-y-2">
        {values.map((value, index) => (
          <div className="flex gap-2" key={index}>
            <Input
              aria-describedby={describedBy}
              aria-invalid={Boolean(error)}
              aria-label={`Reference period ${index + 1}`}
              placeholder={index === 0 ? '1d' : '7d'}
              value={value}
              onChange={(event) => onChange(values.map((item, itemIndex) => (itemIndex === index ? event.target.value : item)))}
            />
            <Button type="button" variant="ghost" aria-label={`Remove reference period ${index + 1}`} onClick={() => onChange(values.filter((_, itemIndex) => itemIndex !== index))}>
              <X size={16} />
            </Button>
          </div>
        ))}
      </div>
      <button type="button" className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-[var(--color-primary)]" onClick={() => onChange([...values, ''])}>
        <Plus size={16} />
        Add reference period
      </button>
      {error ? <p id={errorId} className="mt-1 flex items-center gap-1 text-sm text-[var(--color-error)]"><CircleAlert size={15} aria-hidden="true" />{error}</p> : null}
    </section>
  )
}
