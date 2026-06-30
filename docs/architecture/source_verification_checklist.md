# Source Verification Checklist

The source verification checklist is a report-only manual review layer after source readiness and audit-package evidence.

It does not edit source registry files. It does not create verified source coverage. It records whether an operator has observed the source behaviors needed before any future registry update workflow.

The checklist tracks:

- public entry page
- query behavior
- result list behavior
- detail page behavior
- access barrier such as captcha or login
- terms or access-boundary review
- notes and evidence references

Operator commands:

```text
constructionsight-source-checklist observation-template data/source_registry.seed.json
constructionsight-source-checklist observation-template data/source_registry.seed.json --output data/source_verification_observations.template.json
constructionsight-source-checklist checklist data/source_registry.seed.json
constructionsight-source-checklist checklist data/source_registry.seed.json --json-output
constructionsight-source-checklist checklist data/source_registry.seed.json --check-http
constructionsight-source-checklist checklist data/source_registry.seed.json --observations-path observations.json
```

The observation-template command creates editable JSON with all observation booleans set to `null`. Operators should set booleans only after manual lawful public review. Unknown values should remain `null` instead of being guessed.

The optional observations file is a JSON list of source observations. Each observation may match by `source_key` or `source_name` and may include booleans for entry, query, list, detail, barrier, and terms review.

Checklist output is evidence for review only. Promotion remains a separate future dry-run-first workflow.
