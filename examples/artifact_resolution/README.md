# Artifact Resolution Examples

These fixtures demonstrate governed artifact-based identity resolution without persistence, graph mutation, source access, scraping, or AI/API integration.

They are intended for operator preview, documentation, and regression testing of:

```bash
constructionsight preview-artifact-resolution --input <fixture.json> --json-output
```

## Fixtures

### `commerce_center_match.json`

Demonstrates a probable same-project candidate where two fingerprints converge through:

- shared APN
- shared exact site address
- independent source-family support

Expected decision:

```text
needs_review
```

The score is intentionally below the automatic-link threshold because this fixture shows strong support, but not enough near-unique convergence for an automatic merge.

### `conflicting_ceqa_sch.json`

Demonstrates a rejected match candidate where two fingerprints share a project title but carry conflicting CEQA SCH numbers.

Expected decision:

```text
reject_match
```

## Governance Notes

These fixtures preserve raw values and normalized values separately. They are preview inputs only. They do not authorize any merge, database write, graph mutation, or source search.
