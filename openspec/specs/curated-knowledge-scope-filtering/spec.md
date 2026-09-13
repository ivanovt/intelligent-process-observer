# curated-knowledge-scope-filtering Specification

## Purpose

Apply the independently optional service-version labels of an Observation knowledge scope when selecting approved curated passages for bounded reasoning.

## Requirements

### Requirement: Filter curated knowledge by each scoped service's own optional version

For an Observation with a per-service knowledge scope, the concrete curated retriever SHALL evaluate each service entry independently before lexical or semantic search. An approved active document SHALL be eligible if it is globally applicable or at least one document service tag matches a scoped canonical service ID and that entry's version rule. If the matching scope entry omits a version, tags for that service SHALL be eligible regardless of their supported-version labels. If the entry provides a version, a matching unversioned tag SHALL remain eligible and a matching versioned tag SHALL be eligible only when it contains that exact opaque label. A version selected for one service SHALL not filter another service's tags. When the Observation has no knowledge scope, only global documents SHALL be eligible.

This change SHALL preserve the existing approved-version gate, relevance admission, retrieval budgets, immutable source references, and the separation of knowledge from findings and overall analytical state. The service entries SHALL remain frozen for each run, so a later edit to the Observation Definition SHALL not change that run's eligibility.

#### Scenario: Match one versioned service and one unversioned service independently
- **GIVEN** an Observation scope contains `mprm-server` at `1.0` and `gateway` without a version, with approved documents tagged `mprm-server` at `1.0`, `mprm-server` at `2.0`, `gateway` at `3.0`, and globally
- **WHEN** a finding-grounded retrieval searches the curated corpus
- **THEN** the `mprm-server` `1.0`, `gateway` `3.0`, and global documents are eligible
- **AND** the `mprm-server` `2.0` document is excluded before relevance ranking

#### Scenario: Keep an unversioned tag eligible
- **GIVEN** a scope entry names `mprm-server` at `1.0` and an approved document tags `mprm-server` without supported-version labels
- **WHEN** retrieval searches the curated corpus
- **THEN** that document remains eligible

#### Scenario: Freeze mixed service versions for one run
- **GIVEN** a run starts with `mprm-server` at `1.0` and `gateway` without a version
- **WHEN** the Observation Definition is later changed to other versions before that run's reasoning phase
- **THEN** the run uses its original per-service version choices for retrieval
- **AND** those choices do not enter finding or overall-state model inputs
