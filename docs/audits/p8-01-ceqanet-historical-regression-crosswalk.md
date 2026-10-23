# P8-01 historical CEQAnet test-to-native disposition

**Scope:** historical test behavior, not an authorization to access CEQAnet or a
claim of byte-identical CLI/JSON contracts. The governing baseline is
`docs/audits/p8-01-historical-path-ledger-2026-10-21.json`.
All original files remain available on their named historical Git branches.

**Archived sources inspected:**

- `tests/test_ceqanet_csv_export.py` and `ceqanet_csv_export_{cli,models,service}.py` from `agent/ceqanet-csv-export-contract-v2`.
- `tests/test_ceqanet_ingestion_inbox.py` from `agent/ceqanet-ingestion-dashboard`.
- `tests/test_ceqanet_verified_source_maturity.py` from `agent/ceqanet-evidence-repair-partial-v2`.

## Thirteen archived CSV regressions

| Archived test | Current guarded contract/test | Disposition |
| --- | --- | --- |
| `test_project_url_matches_observed_official_contract` | `test_project_export_request_is_deterministic_and_nonexecuting` | Same canonical official project URL; non-authorizing preview |
| `test_document_url_matches_observed_official_contract` | `test_document_export_request_is_deterministic_and_nonexecuting` | Same official SCH+document URL; non-authorizing preview |
| `test_request_rejects_scope_identity_mismatch` | `test_export_request_rejects_invalid_identities`, `CeqanetCsvExportRequest.require_kind_identity_consistency` | Same positive document-ID-only-document scope restriction |
| `test_parser_preserves_headers_quotes_and_source_text` | `test_project_fixture_inspection_preserves_unknown_columns_and_integrity`, `test_historical_quotes_and_bom_are_supported_with_exact_bytes_digest` | Quoting/BOM/meaningful text and exact response-byte SHA retained. **Not byte-identical output:** normalized field names and stripped display-value padding; see deliberate difference below |
| `test_parser_rejects_duplicate_or_extra_columns` | `test_inspection_rejects_malformed_or_mismatched_bodies`, `test_historical_loose_parser_shapes_are_safely_rejected` | Reject duplicates and extra row fields; additionally reject normalized-header collisions and ambiguous roles |
| `test_execution_requires_explicit_live_authorization` | `test_live_execution_requires_explicit_authorization`, `test_lawful_access_state_blocks_csv_execution_before_transport` | Current requires separate source-specific lawful-access approval, not just a boolean |
| `test_successful_execution_is_tamper_evident_and_verifiable` | `test_successful_live_execution_embeds_canonical_offline_inspection`, `test_live_execution_performs_exactly_one_get_without_redirect_or_retry` | Exact bytes, digest and bounded method observed without persistence/attachment downloads |
| `test_verifier_rejects_body_tampering_even_with_valid_base64` | `test_verifier_rejects_tampered_body_and_digest` | Exact digest/length mismatch detection retained |
| `test_verifier_preserves_http_failure_without_claiming_csv_success` | `test_http_403_is_terminal_without_body_retention_or_bypass`, `test_csv_validation_failure_is_retained_as_evidence` | Fails closed; intentionally **does not retain 403 body** or treat invalid response as successful CSV |
| `test_verifier_rejects_host_query_and_persistence_drift` | `test_export_url_rejects_unapproved_shapes`, `test_verifier_rejects_final_url_identity_drift` and literal-false persistence models | Official HTTPS source, exact query identity, no unauthorized persistence; invalid domain refused before transport |
| `test_plan_cli_emits_request_without_network` | `test_plan_cli_emits_exact_nonexecuting_request` | Functional operator planning behavior retained; CLI flags and output schema intentionally differ |
| `test_parse_and_verify_cli_operate_offline` | `test_inspect_file_cli_writes_digest_bound_artifact`, `test_verify_execution_cli_operates_offline` | Equivalent no-network inspect and retained-execution verification operations; not old subcommand compatibility |
| `test_execution_model_rejects_unknown_fields` | `test_live_model_rejects_unknown_fields` and `CeqanetCsvInspection` exact-schema validation | Unknown fields rejected by current models |

## Three archived inbox regressions

| Archived test | Current guarded test | Disposition |
| --- | --- | --- |
| `test_ingestion_inbox_transitions_from_pending_to_persisted_match` | `test_operator_ingestion_status_tracks_exact_queue_without_writes`, `test_ingestion_inbox_reconciles_pending_persisted_and_conflicting_sch` | Pending-to-reviewed-source claim match preserved; current adds explicit conflict/no-county safeguards |
| `test_ingestion_inbox_rejects_queue_semantic_tampering` | `test_ingestion_inbox_rejects_queue_tampering_before_database_reconciliation`, `test_historical_review_queue_tampering_fails_closed_in_original_and_operator_paths` | Original builder and native HTTP both reject substituted queue identity without writing database |
| `test_operator_exposes_configured_read_only_ingestion_inbox` | `test_operator_ingestion_status_tracks_exact_queue_without_writes`, `test_operator_ingestion_status_is_safe_when_not_configured`, `test_operator_rejects_half_configured_ingestion_evidence` | Configured/unconfigured GET and unknown-query denial, read-only DB; newer operator rejects incomplete evidence configuration |

## One archived verified-maturity regression

| Archived test | Current controls | Disposition |
| --- | --- | --- |
| `test_ceqanet_verified_manual_read_maturity_is_fully_evidenced` | `test_original_native_maturity_matches_independent_original_builders`, `test_native_original_maturity_route_is_read_only_and_exact`, `test_original_maturity_unconfigured_and_rejected_evidence`; P8-03 original manual checklist/source status apply | **Historical certificate only**: original July 12, 2026 verification artifacts remain historical, while current permission must be independently and presently evidenced. Do not resurrect stale registry VERIFIED label, infer live source permission or import an old cert into current policy |

## Intentional differences, not silent parity

1. **Redirect:** old CSV executor called `follow_redirects=True`; current policy terminates redirects with no retry. Restoring the old behavior would weaken source-access controls.
2. **Header-only export:** old `csv.DictReader` returned zero rows as a parse report; current verified source inspection requires an SCH-bearing data row. The new rejection is purposeful: an empty artifact is not affirmative source evidence.
3. **Whitespace:** old `row[header]` held surrounding value whitespace; canonical inspection strips view-value padding and normalizes header keys. Current live receipt retains original full CSV bytes and SHA; an offline inspection independently retains the raw **digest**, not necessarily the bytes. Test this distinction, rather than claim raw string equality.
4. **Failure body:** old non-200 response body was retained and verification reported failure; new 403/302 bodies are not retained, to enforce network/access policy. Both mark failure; byte-retention outputs differ intentionally.
5. **CLI and archived execution artifact:** both versions register the executable `constructionsight-ceqanet-csv`. Current guarded CLI preserves the historic nonexecuting `plan --sch` argument alias, supplies a distinct read-only `parse` command projecting `ceqanet_csv_parse_report.v1` (including original untrimmed source values and header-only archives), and supports offline `verify` (original `ceqanet_csv_export_verification.v1` report fields) and `verify-legacy-execution` (extended non-authorizing integrity/safety report) for archived `ceqanet_csv_export_execution.v1` evidence. These compatibility paths have strict path/source and byte/row limits; internal archive integrity is expressly not current admissibility. The old live `execute --execute-live` command is **not restored**: authorized current collection requires `execute-live` and independent current lawful-access decisions. The new `verify-execution` remains for current-format evidence. Preexisting external old-command consumers and exact error-message compatibility are not certified; no silent network fallback occurs.
6. **Bounds/authorization:** old executor allowed up to 2 MB with an injected HTTP client; new CS-NET-003 uses a bounded 10 MB ceiling, no redirect/retry, exact policy, approved request/access identity and separate human approvals. This does not authorize live use today.

## Workstream boundaries

This crosswalk accounts for all **17 archived tests** in the three missing historical
test files. It does not claim their old modules can run unchanged or that all
historical external automation is known. The native command now provides a
bounded, read-only path to old execution evidence and exact archived parse-report
projection, with safe old `plan --sch` and `verify` aliases. Old live `execute`
network behavior is deliberately superseded by the independently authorized
current `execute-live`, rather than silently restored. The new historical
compatibility tests must pass **exact-head dual-Python CI and native browser**
before P8-01 checkpoint 05 can be accepted. Treat the original network and
historical registry-maturity certificates as historical only; P8-20 separately
requires present lawful-source permission. Historical external clients may
need documented migration even with safe aliases; this is not a claim that
unknown external scripts execute unchanged.
Other changed historical paths (checkpoint 03), result/royalty authority
(checkpoint 06/P8-09), and complete reports/archives (checkpoint 07/P8-11)
are independent and still open. No source activation, new financial rule,
outreach, bid or deployment is authorized by this document.
