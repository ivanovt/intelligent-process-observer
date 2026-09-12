## ADDED Requirements

### Requirement: Form objective-oriented findings without weakening evidence grounding

The finding invocation SHALL use the supplied Observation analytical objective and semantic Lens names/objectives to focus which evidence-grounded conclusions materially answer the Observation's question. The objective and names are context, not evidence: every finding SHALL remain supported only by accepted catalog references, and the model SHALL NOT restate an objective as if it were observed or infer that the objective was achieved, violated, or explained without supporting evidence.

The model SHALL distinguish evidence directly concerning the Observation objective from notable evidence about an auxiliary Lens. When no Relationship evaluation supports a connection, it SHALL NOT claim that one Lens caused, explained, confirmed, or contradicted another. It MAY report both facts separately when each materially helps interpret the Observation.

The model SHALL synthesize mutually reinforcing current, reference-period, and History evidence into a coherent finding when that can be done without losing a materially distinct conclusion or traceability. It SHALL NOT mechanically emit one finding for every field, evidence reference, or temporal perspective. Consolidation SHALL NOT introduce a maximum finding count, ranking, priority, severity, confidence, or suppression of distinct contradictory evidence.

#### Scenario: Answer a connectivity objective with direct and auxiliary evidence

- **GIVEN** the objective concerns device connectivity, the Connected Devices Lens is stable, an auxiliary pod logging Lens has a spike, and no Relationship evaluation links them
- **WHEN** findings are formed
- **THEN** the direct connectivity evidence and the auxiliary logging evidence are distinguished clearly
- **AND** the logging spike is not presented as a cause, confirmation, or contradiction of device connectivity

#### Scenario: Consolidate related temporal evidence

- **GIVEN** one Lens has compatible current state, reference comparison, and sustained History evidence supporting one conclusion
- **WHEN** findings are formed
- **THEN** the model may express that conclusion as one coherent finding citing all relevant evidence
- **AND** it does not split the conclusion solely because the evidence came from different result sections

#### Scenario: Preserve materially distinct or conflicting evidence

- **GIVEN** two evidence-backed conclusions are materially distinct or conflict
- **WHEN** finding consolidation is considered
- **THEN** both conclusions remain explicitly represented with their own traceability
- **AND** consolidation does not hide uncertainty or manufacture agreement

#### Scenario: Keep the objective out of the evidence chain

- **GIVEN** the analytical objective contains an assertion not supported by the evidence catalog
- **WHEN** finding output is validated and evaluated
- **THEN** no finding treats that assertion as observed evidence
- **AND** every accepted finding still cites one or more supplied catalog IDs

### Requirement: Preserve Metric comparison semantics in authored findings

When Metric evidence contains `relative_level_change`, finding guidance SHALL identify it as the accepted symmetric dimensionless comparison:

```text
2 * (current_mean - reference_mean)
  / (abs(current_mean) + abs(reference_mean))
```

The model SHALL NOT describe `relative_level_change * 100` as an ordinary percentage increase or decrease. When communicating the magnitude in natural language, it SHALL either call the value a symmetric relative change or cite the current and reference means without converting the symmetric value into conventional percentage language. This requirement changes no Metric calculation, threshold, relation, or persisted evidence.

#### Scenario: Avoid a false percentage interpretation

- **GIVEN** current mean `2.28`, reference mean `1.04`, and `relative_level_change=0.7456`
- **WHEN** a finding presents the comparison
- **THEN** it does not say the current mean is “74.56% higher”
- **AND** it instead identifies a symmetric relative change of approximately `0.746` or presents both means

#### Scenario: Preserve qualitative relation

- **GIVEN** the deterministic reference result says current level is `higher`
- **WHEN** the finding paraphrases that relation
- **THEN** it preserves the current-versus-reference orientation
- **AND** it does not recalculate or replace the accepted relation

### Requirement: Select overall state from significance and evidence availability rather than item count

The knowledge-isolated overall-state invocation SHALL receive server-owned guidance that applies the accepted state meanings: `significant_findings_present` when the evidence-grounded findings include one or more conclusions deserving attention; `no_significant_findings` when the available evidence supports no significant conclusion; and `uncertain` when evidence availability prevents a reliable overall assessment. The model SHALL evaluate the content and evidence availability, not map mechanically from the number of findings or treat every descriptive finding as significant.

No deterministic count invariant, new state, severity, confidence, probability, or ranking SHALL be added. Valid findings MAY coexist with `uncertain`, and a descriptive finding that directly answers an objective without indicating a concern SHALL NOT alone force `significant_findings_present`.

#### Scenario: Keep stable objective evidence from forcing significance

- **GIVEN** a finding states that the directly relevant Metric remained stable and no other finding deserves attention
- **WHEN** overall state is determined
- **THEN** finding count alone does not force `significant_findings_present`
- **AND** the selected state follows the accepted evidence-based meanings

#### Scenario: Preserve significance for a notable auxiliary finding

- **GIVEN** direct objective evidence is stable but a separate evidence-grounded finding deserves attention
- **WHEN** overall state is determined
- **THEN** `significant_findings_present` remains available without claiming a causal relationship
- **AND** no severity or ranking is added to identify that finding

#### Scenario: Preserve uncertainty with findings

- **GIVEN** valid findings exist and deterministic limitations show material evidence unavailability
- **WHEN** the model cannot make a reliable overall assessment
- **THEN** it may return `uncertain`
- **AND** the findings remain unchanged
