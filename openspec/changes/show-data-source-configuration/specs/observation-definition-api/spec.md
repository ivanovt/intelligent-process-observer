## MODIFIED Requirements

### Requirement: Discover enabled Metric acquisition capabilities

The system SHALL expose `GET /api/v1/observation-definition-capabilities`. It SHALL return the enabled Metric adapter type `prometheus` and compatible source entries in configured order. Each source entry SHALL contain its stable ID, human-readable name, and a typed `configuration` projection containing all currently supported non-secret environment configuration fields.

For a Prometheus source, `configuration` SHALL contain the exact configured `id`, `name`, and `base_url`, plus a `credentials` object. Bearer-token credentials SHALL project only exact `type: bearer_token`. Basic-auth credentials SHALL project exact `type: basic_auth` and the configured `username`. The response SHALL omit bearer tokens and Basic-auth passwords entirely and SHALL NOT serialize masked values, secret representations, Authorization data, raw environment JSON, connection health, or provider diagnostics. Adding another field to server-side source settings SHALL NOT expose it through this API unless the public projection contract is explicitly extended.

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
