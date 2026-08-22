## Why

The MVP needs persisted, engineer-authored Observation configuration before it can later instantiate any execution workflow. Clients currently cannot create or navigate predefined Observation definitions, their Lens definitions, or their engineer-defined Metric Relationships.

## What Changes

- Add atomic creation and persisted reads for predefined Observation definitions with owned Lenses and Metric-only Relationships.
- Add compact linked list results, complete Observation detail, and individual Lens/Relationship detail reads.
- Define versioned typed contracts for Metric, Alert, and Log Lens configuration, deployment capability discovery, and non-persisting Lens preflight validation.
- Reject invalid aggregate topology, adapter/source references, and Relationship vocabulary without partially persisting a definition.
- Keep definitions distinct from all runs, results, policies, scheduling, and execution behavior.

## Capabilities

### New Capabilities

- `observation-definition-api`: Persist, validate, navigate, and preflight predefined Observation definitions with Lens and Metric-Relationship configuration.

### Modified Capabilities

None.

## Impact

- Affected backend: API contracts/routes, domain validation, capability discovery, persistence/migration, and tests.
- No frontend, Observation/Lens runtime endpoint, dependency, or architecture-document change is proposed.
- Concrete Alert/Log preflight execution remains blocked by unresolved Jira Track and Release/Loki integration contracts; this change does not invent them.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md`
- `docs/architecture/02_architecture_principles_and_runtime.md`
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`
- `docs/architecture/10_open_decisions_and_backlog.md`
- `docs/architecture/11_glossary_and_naming.md`
- `docs/architecture/03_ADR_log.md` — ADR-001, ADR-003–011, ADR-043–063, ADR-088–091, ADR-133, ADR-136–138.
