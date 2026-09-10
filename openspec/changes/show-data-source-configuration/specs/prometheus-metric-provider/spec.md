## MODIFIED Requirements

### Requirement: Resolve a server-managed Prometheus source without exposing credentials

The system SHALL resolve the immutable Metric provider scope's `source_id` against the
existing server-managed `PROMETHEUS_SOURCES` registry. This change SHALL NOT make global
Settings construction or shared source-registry loading stricter and SHALL NOT alter
Observation creation or Metric preflight behavior. The definition-capabilities response
MAY expose only the explicitly typed non-secret source projection defined by the
Observation Definition API contract; that projection SHALL NOT represent production
target validation or connection health. Production-only URL and transport validation
SHALL occur only after the `MetricSeriesProvider` resolves the selected configured source
for an acquisition.

A configured source SHALL retain its existing stable ID, human-readable name, base URL,
and exactly one existing credential mode: Bearer token or HTTP Basic username/password.
For this capability, **secret credential material** means exactly the Bearer token and
Basic-auth password. The existing Basic username is not secret credential material and
MAY remain in the internal configuration model and appear only in the approved
definition-capabilities projection. The provider SHALL send Bearer credentials in
`Authorization: Bearer <token>` or Basic credentials preemptively and SHALL never put
credentials in the URL. Provider ports, diagnostics, logs, errors, failure messages, and
all other public output SHALL expose none of the Bearer token, Basic password,
Authorization header, or configured Basic username. This change SHALL NOT modify the
existing credential model merely to change its internal representation.

At production acquisition, the selected source base URL SHALL use HTTPS except that HTTP
MAY be used for the exact loopback hosts `localhost`, `127.0.0.1`, or `::1`. It SHALL
contain a host and SHALL contain no userinfo, query, or fragment. The provider SHALL
verify TLS by default, ignore process proxy environment variables, and not follow
redirects. Custom CA bundles, mutual TLS, OAuth, cloud-vendor signing, unauthenticated
sources, and proxy configuration are outside this capability.

Secret credential material SHALL be accepted only through local/deployment environment
configuration and SHALL NOT appear in an Observation definition, LensRun, Metric result,
public API response, committed example value, URL, log, error, failure message, or
diagnostic. An absent registry or unknown `source_id` SHALL yield the existing typed
unavailable provider outcome and SHALL NOT select a different or default source. A
configured source that shared loading accepts but production-only URL/transport
validation rejects SHALL yield `MetricSeriesAcquisitionFailure` with zero HTTP attempts;
application startup, Observation creation, and Metric-preflight behavior SHALL remain
unchanged, and capabilities SHALL continue to return the source's approved non-secret
projection without implying production validity or health.

#### Scenario: Resolve a configured source by exact ID

- **GIVEN** the immutable provider scope names one valid configured Prometheus source
- **WHEN** Metric acquisition is composed
- **THEN** the provider uses only that source's normalized API target and credentials
- **AND** it does not expose the connection configuration across the provider port

#### Scenario: Keep a Prometheus credential secret

- **WHEN** a Bearer token or Basic password is supplied through deployment configuration
- **THEN** it is used only for the outbound Prometheus request
- **AND** no committed file, runtime artifact, public response, or diagnostic contains it

#### Scenario: Keep the internal Basic username compatible but out of failures

- **GIVEN** an existing configured source contains a Basic-auth username
- **WHEN** shared configuration is loaded, capabilities are read, and production acquisition is attempted
- **THEN** the definition-capabilities response may include that username only in its approved non-secret configuration projection
- **AND** provider ports, diagnostics, logs, errors, failure messages, and all other public output expose neither that username nor any secret credential material

#### Scenario: Report an unavailable source safely

- **GIVEN** no source registry is configured or the requested `source_id` is absent
- **WHEN** the provider acquires a current or reference window
- **THEN** it returns the typed unavailable outcome with a fixed safe diagnostic category
- **AND** it performs zero HTTP attempts and selects no fallback source

#### Scenario: Reject an unsafe authenticated target

- **GIVEN** a source URL contains non-loopback HTTP, userinfo, no host, a query, or a fragment
- **WHEN** that configured source is selected for production Metric acquisition
- **THEN** zero HTTP attempts are performed
- **AND** acquisition returns `MetricSeriesAcquisitionFailure` with a fixed safe diagnostic

#### Scenario: Preserve shared source consumers for a production-invalid source

- **GIVEN** shared source loading accepts a configured source that production-only URL or transport validation rejects
- **WHEN** the application starts and capabilities, Observation creation, Metric preflight, and production Metric acquisition are exercised
- **THEN** startup succeeds, capabilities return only the approved non-secret configuration projection, and creation and preflight retain their existing behavior
- **AND** only production acquisition returns `MetricSeriesAcquisitionFailure` with zero HTTP attempts

