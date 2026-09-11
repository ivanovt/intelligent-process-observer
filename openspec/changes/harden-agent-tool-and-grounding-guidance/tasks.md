## 1. Metric interaction guidance

- [ ] 1.1 Add focused failing adapter tests that inspect a usable Metric invocation for non-parallel tool request settings, one-call-per-response guidance, empty arguments, single-use tools, the three-attempt ceiling, strict completion guidance, and distinct capability-specific tool descriptions; verify the new tests fail for the current minimal prompt/settings.
- [ ] 1.2 Add focused coverage proving an insufficient Metric invocation remains tool-free and does not gain optional-analysis behavior; verify the focused Metric adapter test module passes after implementation.
- [ ] 1.3 Introduce the private Metric instruction constant and fixed capability-specific tool descriptions, and derive request-local settings with `parallel_tool_calls=false` only when optional tools are exposed; verify existing scripted parallel, duplicate, invalid, and over-budget responses retain their exact rejection and partial-result mappings.

## 2. Hypothesis grounding guidance

- [ ] 2.1 Add focused failing reasoning-adapter tests that inspect the hypothesis invocation for non-parallel retrieval settings and guidance covering optional retrieval, frozen-finding anchors, independent/refinement rules, exact direct-or-preserved-upstream references, untrusted knowledge, and `hypotheses=[]` when neither source makes a reference available; verify the new tests fail for the current minimal prompt/settings.
- [ ] 2.2 Add focused coverage proving finding and overall-state invocations remain tool-free and that scripted parallel retrieval or invented knowledge references still fail through the existing deterministic policy/grounding paths; verify no request budget, retry, or failure-code expectation changes.
- [ ] 2.3 Introduce the private hypothesis instruction constant and apply `parallel_tool_calls=false` only to hypothesis model requests; verify focused reasoning adapter and executor tests pass, including empty, failed, and timed-out retrieval outcomes followed by a compliant empty hypothesis completion.

## 3. Developer verification

- [ ] 3.1 Document an opt-in Home DEV smoke procedure that enables development traces, launches the existing Observation, locates artifacts by `observation_run_id`, and checks sequential Metric tool calls plus absence of fabricated hypothesis knowledge references without copying trace contents into Git; verify the documented commands and artifact locations match the runtime-observability guide.
- [ ] 3.2 Run the focused Metric, reasoning, production-composition, and agent-tracing test modules and verify all existing deterministic rejection, budgets, grounding, trace, and safe-diagnostic assertions pass.
- [ ] 3.3 With valid local OpenRouter and Home DEV settings, perform the documented trace-backed smoke run and record only the run ID and pass/fail observations in the implementation handoff; if the target model still violates the contract, retain deterministic failure behavior and report the trace evidence for a separately approved model/default or evaluation change.
- [ ] 3.4 Run `make check` as the final local verification gate and verify backend tests, frontend lint/tests/build, Ruff checks, and strict OpenSpec validation all pass before implementation review, archive, and pull-request preparation.
