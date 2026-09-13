export type KnowledgeDocumentType = 'official_document' | 'runbook' | 'maintenance_guide' | 'incident' | 'operator_journal'
export type KnowledgeAuthority = 'official' | 'internal_approved' | 'operator_authored'

/** Declares one service applicability tag retained with an immutable source version. */
export interface ServiceTag { service_id: string; aliases: string[]; supported_versions: string[] }
/** Immutable metadata and lifecycle state for one retained source version. */
export interface KnowledgeVersion { version: number; title: string; document_type: KnowledgeDocumentType; authority: KnowledgeAuthority; owner: string; source_reference: string | null; media_type: string; content_hash: string; extraction_state: 'pending' | 'ready' | 'failed'; lifecycle_state: 'imported' | 'approved' | 'deprecated'; service_tags: ServiceTag[] }
/** A document identity plus its immutable retained source-version history. */
export interface KnowledgeDocument { id: string; title: string; document_type: KnowledgeDocumentType; authority: KnowledgeAuthority; service_tags: ServiceTag[]; active_version: number | null; versions?: KnowledgeVersion[] }
/** An inert exact chunk projection resolved from a version-specific locator. */
export interface KnowledgeChunk { ordinal: number; location: string; text: string }
/** Metadata submitted before the original source bytes are retained. */
export interface KnowledgeUploadMetadata { title: string; document_type: KnowledgeDocumentType; authority: KnowledgeAuthority; owner: string; source_reference: string | null; service_tags: ServiceTag[] }
/** Validated immutable curated-corpus citation locator. */
export type CuratedKnowledgeLocator = { reference: string; ordinal: number; page: number | null }
export class KnowledgeApiError extends Error { readonly status: number; constructor(status: number, message: string) { super(message); this.status = status } }

const base = '/api/v1/knowledge'
const sourcePattern = /^knowledge-document:([0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}):v([1-9][0-9]*)$/i
const pdfLocatorPattern = /^pdf:page:([1-9][0-9]*):chunk:([1-9][0-9]*)$/
const markdownLocatorPattern = /^md:chunk:([1-9][0-9]*)$/

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${base}${path}`, init)
  if (!response.ok) {
    let message = 'Knowledge request failed.'
    try { message = (await response.json() as { message?: string }).message ?? message } catch { /* keep safe error */ }
    throw new KnowledgeApiError(response.status, message)
  }
  return response.json() as Promise<T>
}

/** Parses only the approved immutable PDF or Markdown chunk syntax. */
export function parseCuratedLocator(reference: string): CuratedKnowledgeLocator | null {
  const pdf = pdfLocatorPattern.exec(reference)
  if (pdf) return { reference, page: Number(pdf[1]), ordinal: Number(pdf[2]) }
  const markdown = markdownLocatorPattern.exec(reference)
  return markdown ? { reference, page: null, ordinal: Number(markdown[1]) } : null
}

/** Builds a local destination only for a fully recognized immutable curated citation. */
export function knowledgeCitationDestination(reference: { source_id: string; reference: string }): string | null {
  const source = sourcePattern.exec(reference.source_id)
  const locator = parseCuratedLocator(reference.reference)
  if (!source || !locator) return null
  const query = new URLSearchParams({ document: source[1], version: source[2], reference: locator.reference })
  return `/knowledge?${query.toString()}`
}

/** Lists manually managed knowledge documents. */
export function listKnowledgeDocuments(signal?: AbortSignal) { return request<KnowledgeDocument[]>('/documents', { signal }) }
/** Loads one document and its immutable version history. */
export function getKnowledgeDocument(id: string, signal?: AbortSignal) { return request<KnowledgeDocument>(`/documents/${encodeURIComponent(id)}`, { signal }) }
/** Resolves an exact version-local citation without translating PDF page-local ordinals. */
export function getKnowledgeChunk(id: string, version: number, locator: CuratedKnowledgeLocator, signal?: AbortSignal) {
  const page = locator.page === null ? '' : `?page=${encodeURIComponent(String(locator.page))}`
  return request<KnowledgeChunk>(`/documents/${encodeURIComponent(id)}/versions/${version}/chunks/${locator.ordinal}${page}`, { signal })
}
/** Uploads a new immutable document or a later immutable version of an existing document. */
export function uploadKnowledgeDocument(file: File, metadata: KnowledgeUploadMetadata, documentId?: string, signal?: AbortSignal) {
  const body = new FormData(); body.append('file', file); body.append('metadata', JSON.stringify(metadata))
  const path = documentId ? `/documents/${encodeURIComponent(documentId)}/versions` : '/documents'
  return request<KnowledgeDocument>(path, { method: 'POST', body, signal })
}
/** Runs an explicit retained-source extraction retry. */
export function retryExtraction(id: string, version: number, signal?: AbortSignal) { return request<KnowledgeDocument>(`/documents/${encodeURIComponent(id)}/versions/${version}/retry-extraction`, { method: 'POST', signal }) }
/** Publishes a ready immutable version for retrieval after explicit disclosure confirmation. */
export function approveVersion(id: string, version: number, signal?: AbortSignal) { return request<KnowledgeDocument>(`/documents/${encodeURIComponent(id)}/versions/${version}/approve`, { method: 'POST', signal }) }
/** Removes one approved version from retrieval eligibility after explicit confirmation. */
export function deprecateVersion(id: string, version: number, signal?: AbortSignal) { return request<KnowledgeDocument>(`/documents/${encodeURIComponent(id)}/versions/${version}/deprecate`, { method: 'POST', signal }) }
/** Returns the attachment-only retained source URL for one immutable version. */
export function sourceDownloadHref(id: string, version: number) { return `${base}/documents/${encodeURIComponent(id)}/versions/${version}/source` }
