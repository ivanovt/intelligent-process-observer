## MODIFIED Requirements

### Requirement: Keep provider transport and production model selection outside the pipeline capability

The pipeline capability SHALL consume injected provider and agent boundaries. It SHALL
not contain a Jira Track and Release endpoint, API field mapping, transport,
authentication, credentials, retry/backoff policy, pagination/truncation policy,
production model or provider selection, provider-specific model settings, or external
live calls. A separately specified Jira Alert provider MAY implement those concerns
behind the existing injected AlertProvider port; it SHALL not alter the pipeline's
provider-neutral acquisition, normalization, analytical, agent, result, or persistence
contracts. The existing PydanticAI dependency, where used, SHALL remain in an
infrastructure adapter behind the framework-neutral agent boundary.

#### Scenario: Exercise the pipeline without live integrations

- **GIVEN** deterministic fake provider and agent implementations
- **WHEN** the pipeline contract is exercised in tests
- **THEN** current/reference, agent, result, and persistence behavior is verifiable
- **AND** no Jira credential, network transport, or production model configuration is required

#### Scenario: Supply a production provider without changing pipeline semantics

- **GIVEN** a separately configured Jira provider is injected through AlertProvider
- **WHEN** it returns an existing typed acquisition outcome for an immutable window
- **THEN** the pipeline applies the same current/reference outcome and normalization
  rules as for a fake provider
- **AND** Jira transport details remain outside the pipeline capability
