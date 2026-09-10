## MODIFIED Requirements

### Requirement: Discover enabled Metric acquisition capabilities

The system SHALL expose `GET /api/v1/observation-definition-capabilities`. It SHALL return the enabled Metric adapter type `prometheus` and compatible source entries in configured order. Each source entry SHALL contain its stable ID, human-readable name, and a typed `configuration` projection containing the currently supported fields that are safe for public inspection.

For a Prometheus source, `configuration` SHALL contain the exact configured `id` and `name`, plus a `credentials` object. Bearer-token credentials SHALL project only exact `type: bearer_token`. Basic-auth credentials SHALL project exact `type: basic_auth` and the configured `username`.

The projection SHALL include the exact configured `base_url` only when that complete value passes the existing production-safe Prometheus target validation. When the value fails that validation, `base_url` SHALL be absent from the serialized configuration object; the response SHALL NOT return the rejected value, a normalized or redacted substitute, a placeholder, a reason, or a validity/health indicator. This omission is a confidentiality boundary and SHALL NOT make capabilities responsible for production target validation or connection health.

The response SHALL omit bearer tokens and Basic-auth passwords entirely and SHALL NOT serialize masked values, secret representations, Authorization data, raw environment JSON, connection health, or provider diagnostics. Adding another field to server-side source settings SHALL NOT expose it through this API unless the public projection contract is explicitly extended.

#### Scenario: Read enabled sources

- **GIVEN** configured sources are enabled
- **WHEN** the client requests the capability endpoint
- **THEN** the system returns `200 OK` with Metric Lens type, `prometheus`, source ID, source name, and the typed non-secret configuration projection
- **AND** it returns no bearer token, Basic-auth password, masked secret, Authorization data, raw environment JSON, health state, or diagnostic

#### Scenario: Read a Bearer-token source safely

- **GIVEN** an enabled Prometheus source uses Bearer-token credentials
- **WHEN** the client requests the capability endpoint
- **THEN** the system returns `200 OK` with its adapter type, source ID, source name, base URL, and credential type
- **AND** the response contains no token field, token value, masked token, Authorization data, raw environment JSON, health state, or diagnostic

#### Scenario: Read a Basic-auth source safely

- **GIVEN** an enabled Prometheus source uses Basic-auth credentials
- **WHEN** the client requests the capability endpoint
- **THEN** the system returns `200 OK` with its adapter type, source ID, source name, base URL, credential type, and username
- **AND** the response contains no password field, password value, masked password, Authorization data, raw environment JSON, health state, or diagnostic

#### Scenario: Preserve configured source order

- **GIVEN** multiple Prometheus sources are enabled
- **WHEN** the client requests the capability endpoint
- **THEN** the system returns each source once in configured order

#### Scenario: Omit an unsafe configured base URL

- **GIVEN** shared source loading accepts a configured `base_url` that fails the existing production-safe target validation, including a URL containing userinfo with an embedded password
- **WHEN** the client requests the capability endpoint
- **THEN** the source remains present with its exact ID, name, and safe credential projection
- **AND** `base_url`, the rejected URL, its userinfo, embedded password, query, fragment, and any redacted or normalized substitute are absent from the serialized response
- **AND** the response contains no reason, validity state, connection-health state, or provider diagnostic
