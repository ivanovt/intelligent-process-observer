import { cloneElement, forwardRef, useId, type AriaAttributes, type ButtonHTMLAttributes, type InputHTMLAttributes, type MouseEvent as ReactMouseEvent, type ReactElement, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'
import { CheckCircle2, CircleAlert, Info, TriangleAlert, type LucideIcon } from 'lucide-react'
import { Link, type LinkProps } from 'react-router-dom'
import { twMerge } from 'tailwind-merge'

function cn(...values: Parameters<typeof clsx>) {
  return twMerge(clsx(values))
}

/** Shared visual variants for buttons and button-like navigation actions. */
const actionStyles = cva(
  'inline-flex h-10 min-h-10 shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-lg px-4 text-sm font-medium leading-none transition-colors focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-[color-mix(in_srgb,var(--color-focus),transparent_70%)] disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-55',
  {
    variants: {
      variant: {
        primary: 'bg-[var(--color-primary)] text-white shadow-sm hover:bg-[var(--color-primary-hover)] active:bg-[var(--color-primary-active)]',
        secondary: 'border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-primary)] shadow-sm hover:bg-[var(--color-surface-muted)]',
        ghost: 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-muted)] hover:text-[var(--color-text-primary)]',
      },
    },
    defaultVariants: { variant: 'primary' },
  },
)

type ActionVariant = VariantProps<typeof actionStyles>['variant']

/** Renders a consistently sized action control. */
export function Button({ className, variant, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ActionVariant }) {
  return <button className={cn(actionStyles({ variant }), className)} {...props} />
}

/** Renders client-side navigation with the same visual treatment as a Button. */
export function ActionLink({ className, disabled = false, onClick, variant, ...props }: LinkProps & { disabled?: boolean; variant?: ActionVariant }) {
  return (
    <Link
      {...props}
      aria-disabled={disabled || undefined}
      className={cn(actionStyles({ variant }), disabled && 'pointer-events-none cursor-not-allowed opacity-55', className)}
      onClick={(event) => {
        if (disabled) {
          event.preventDefault()
          return
        }
        onClick?.(event)
      }}
      tabIndex={disabled ? -1 : undefined}
    />
  )
}

/** Renders a page title, optional supporting context, and aligned page-level actions. */
export function PageHeader({ actions, className, description, eyebrow, title }: { actions?: ReactNode; className?: string; description?: ReactNode; eyebrow?: ReactNode; title: ReactNode }) {
  return (
    <header className={cn('mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between', className)}>
      <div className="min-w-0">
        {eyebrow ? <p className="text-sm text-[var(--color-text-secondary)]">{eyebrow}</p> : null}
        <h1 className={cn('font-semibold tracking-tight text-[var(--color-text-primary)]', eyebrow ? 'mt-1 text-[28px]' : 'text-3xl')}>{title}</h1>
        {description ? <p className="mt-2 max-w-3xl text-[var(--color-text-secondary)]">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-3 self-start sm:justify-end">{actions}</div> : null}
    </header>
  )
}

/** Keeps form actions and supporting context together while a desktop configuration page scrolls. */
export function FormSideRail({ actions, children, className }: { actions: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={cn('self-start lg:sticky lg:top-6 lg:z-10', className)}>
      <div className="flex flex-wrap items-center gap-3 lg:justify-end">{actions}</div>
      <div className="mt-5 lg:mt-20">{children}</div>
    </div>
  )
}

/** Renders a compact single-line text input. */
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...props }, ref) {
  return <input ref={ref} className={cn('h-10 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-sm shadow-xs outline-none transition-colors placeholder:text-[var(--color-text-secondary)] hover:border-[var(--color-border-strong)] focus:border-[var(--color-focus)] aria-[invalid=true]:border-[var(--color-error-border)] aria-[invalid=true]:ring-2 aria-[invalid=true]:ring-[var(--color-error-focus)] disabled:cursor-not-allowed disabled:bg-[var(--color-surface-muted)] disabled:text-[var(--color-text-secondary)]', className)} {...props} />
})

/** Renders a compact multiline text input. */
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, ...props }, ref) {
  return <textarea ref={ref} className={cn('min-h-24 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm shadow-xs outline-none transition-colors placeholder:text-[var(--color-text-secondary)] hover:border-[var(--color-border-strong)] focus:border-[var(--color-focus)] aria-[invalid=true]:border-[var(--color-error-border)] aria-[invalid=true]:ring-2 aria-[invalid=true]:ring-[var(--color-error-focus)] disabled:cursor-not-allowed disabled:bg-[var(--color-surface-muted)] disabled:text-[var(--color-text-secondary)]', className)} {...props} />
})

/** Renders a compact native select control. */
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select({ className, ...props }, ref) {
  return <select ref={ref} className={cn('h-10 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-sm shadow-xs outline-none transition-colors hover:border-[var(--color-border-strong)] focus:border-[var(--color-focus)] aria-[invalid=true]:border-[var(--color-error-border)] aria-[invalid=true]:ring-2 aria-[invalid=true]:ring-[var(--color-error-focus)] disabled:cursor-not-allowed disabled:bg-[var(--color-surface-muted)] disabled:text-[var(--color-text-secondary)]', className)} {...props} />
})

type FieldControlProps = Pick<AriaAttributes, 'aria-describedby' | 'aria-invalid'> & { className?: string; id?: string }

/** Configuration for a labelled form control and its accessible supporting text. */
export interface FieldProps {
  /** The visible label for the control; callers may include optional-field wording. */
  label: ReactNode
  /** A single control that accepts standard ARIA description and invalid-state attributes. */
  children: ReactElement<FieldControlProps>
  /** Persistent, neutral guidance that explains what the control expects. */
  description?: ReactNode
  /** Validation feedback shown after the control when its value is invalid. */
  error?: ReactNode
}

/** Groups a labelled control with persistent guidance and validation feedback. */
export function Field({ label, children, description, error }: FieldProps) {
  const fieldId = useId().replace(/:/g, '')
  const controlId = children.props.id ?? `${fieldId}-control`
  const descriptionId = description ? `${fieldId}-description` : undefined
  const errorId = error ? `${fieldId}-error` : undefined
  const describedBy = [children.props['aria-describedby'], descriptionId, errorId].filter(Boolean).join(' ') || undefined
  const ariaInvalid = children.props['aria-invalid'] ?? (error ? true : undefined)
  const control = cloneElement(children, {
    id: controlId,
    ...(describedBy ? { 'aria-describedby': describedBy } : {}),
    ...(ariaInvalid !== undefined ? { 'aria-invalid': ariaInvalid } : {}),
  })

  return (
    <div className="grid gap-1.5 text-sm font-medium">
      <label htmlFor={controlId}>{label}</label>
      {control}
      {description ? <span id={descriptionId} className="text-xs font-normal text-[var(--color-text-secondary)]">{description}</span> : null}
      {error ? <span id={errorId} className="flex items-center gap-1 text-xs font-normal text-[var(--color-error)]"><CircleAlert size={14} aria-hidden="true" />{error}</span> : null}
    </div>
  )
}

type NoticeTone = 'info' | 'warning' | 'error' | 'success'

const noticeTone: Record<NoticeTone, { icon: LucideIcon; styles: string }> = {
  info: { icon: Info, styles: 'border-[var(--color-info-border)] bg-[var(--color-info-surface)] text-[var(--color-info)]' },
  warning: { icon: TriangleAlert, styles: 'border-[var(--color-warning-border)] bg-[var(--color-warning-surface)] text-[var(--color-warning)]' },
  error: { icon: CircleAlert, styles: 'border-[var(--color-error-border)] bg-[var(--color-error-surface)] text-[var(--color-error)]' },
  success: { icon: CheckCircle2, styles: 'border-[var(--color-success-border)] bg-[var(--color-success-surface)] text-[var(--color-success)]' },
}

/** Displays a contained operational or configuration notice with a semantic tone. */
export function InlineNotice({ children, tone = 'info' }: { children: ReactNode; tone?: NoticeTone }) {
  const Icon = noticeTone[tone].icon
  return <div role={tone === 'error' ? 'alert' : 'status'} className={cn('flex items-start gap-2 rounded-lg border px-4 py-3 text-sm', noticeTone[tone].styles)}><Icon className="mt-0.5 shrink-0" size={17} aria-hidden="true" /><div>{children}</div></div>
}

/** One normalized blocking issue in a validation summary. */
export interface ValidationIssue { linkLabel?: ReactNode; message: ReactNode; to?: string }

function navigateToLocalIssue(event: ReactMouseEvent<HTMLAnchorElement>, targetHash: string) {
  const target = document.getElementById(decodeURIComponent(targetHash.slice(1)))
  if (!target) return
  event.preventDefault()
  if (window.location.hash !== targetHash) window.history.pushState(window.history.state, '', targetHash)
  target.scrollIntoView({ block: 'center' })
  if (target.matches('input, textarea, select, button, [tabindex]:not([tabindex="-1"])')) target.focus({ preventScroll: true })
}

/** Presents one focusable, assertive starting point for an invalid form submission. */
export const ValidationSummary = forwardRef<HTMLDivElement, { issues: ValidationIssue[]; title?: string }>(function ValidationSummary({ issues, title = 'Issues need attention' }, ref) {
  return <div ref={ref} tabIndex={-1} role="alert" aria-labelledby="validation-summary-heading" className="rounded-xl border border-[var(--color-error-border)] bg-[var(--color-error-surface)] p-4 text-sm text-[var(--color-error)] focus:outline-none focus:ring-3 focus:ring-[var(--color-error-focus)]"><div className="flex items-start gap-2"><CircleAlert className="mt-0.5 shrink-0" size={18} aria-hidden="true" /><div><h2 id="validation-summary-heading" className="font-semibold">{title}</h2><p className="mt-1">{issues.length} issue{issues.length === 1 ? '' : 's'} need attention.</p></div></div><ol className="mt-3 list-decimal space-y-1 pl-6">{issues.map((issue, index) => <li key={index}>{issue.message}{issue.to ? <> {issue.to.startsWith('#') ? <a className="font-medium underline underline-offset-2" href={issue.to} onClick={(event) => navigateToLocalIssue(event, issue.to!)}>{issue.linkLabel ?? 'Correct this issue'}</a> : <Link className="font-medium underline underline-offset-2" to={issue.to}>{issue.linkLabel ?? 'Correct this issue'}</Link>}</> : null}</li>)}</ol></div>
})
