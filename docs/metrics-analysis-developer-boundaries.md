# Metrics analysis pipeline developer boundaries

The Metrics pipeline is composed with injected internal ports. Create
`MetricAnalysisPipeline` with a `MetricSeriesProvider`, `MetricsAnalysisAgent`,
`MetricHistoryReader`, and the existing `RuntimePersistenceRepository`; supply an
already-running `MetricLensExecutionContext`. The caller runs `analyze()` before
opening its transaction, then calls `persist_terminal()` inside the caller-owned
transaction. The pipeline does not create runs or commit transactions.

The PydanticAI adapter is an infrastructure implementation of
`MetricsAnalysisAgent`. Construct it with an already selected PydanticAI `Model`.
It must not select a model name, credentials, provider, or transport, and domain
contracts must remain free of PydanticAI types.

`MetricResultBuilder` is the accepted owner of strict `MetricAnalysisResult` 1.0
construction. Providers and agent adapters return typed port outcomes only; they
must not construct result payloads, advance LensRun state, or persist artifacts.

A future Prometheus implementation belongs behind `MetricSeriesProvider` in
infrastructure. It may translate provider-specific query/authentication/retry
behavior into the existing typed acquisition outcomes, but must not widen the
immutable provider scope, choose a window, or introduce transport objects into
the Metrics domain or result contract.
