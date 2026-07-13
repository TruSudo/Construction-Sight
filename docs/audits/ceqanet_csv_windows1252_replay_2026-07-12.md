# CEQAnet Windows-1252 Offline Replay

Replayed at: `2026-07-13T20:08:38.199946+00:00`

## Source evidence

- Source execution digest: `9a861dcee42092eb6f2d8f5c86673f4aca4c75cd0d42beddaa930cc093221a95`
- Source request URL: `https://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=2026030377`
- Source HTTP status: `200`
- Source body bytes: `7832`
- Source body SHA-256: `5b1bc503c81d12ed0f00e52539edb437b42ae4c3a539a25e1c82a02b84273163`
- New network request: `false`
- Persistence mutated: `false`

## Corrected inspection

- Encoding: `windows-1252`
- Content type: `text/csv`
- Columns: `55`
- Rows: `2`
- Retained rows: `2`
- Rows truncated: `false`
- Normalized headers: `["sch_number", "lead_agency_name", "lead_agency_title", "lead_agency_acronym", "document_title", "document_type", "received", "posted", "document_description", "document_portal_url", "project_title", "contact_full_name", "contact_authority", "contact_job_title", "contact_email_address", "contact_address_1", "contact_address_2", "contact_city", "contact_state", "contact_zip_code", "contact_phone_number", "location_coordinates", "cities", "counties", "county_clerks", "location_cross_streets", "location_zip_code", "location_total_acres", "location_parcel_number", "location_state_highways", "location_waterways", "location_airports", "noc_has_non_late_comment", "noc_state_review_start_date", "noc_state_review_end_date", "noc_development_type", "noc_local_action", "noc_project_issues", "noc_public_review_start_date", "noc_public_review_end_date", "noe_exempt_status", "noe_exempt_citation", "noe_reasons_for_exemption", "nod_agency", "nod_approved_by_lead_agency", "nod_approved_date", "nod_significant_environmental_impact", "nod_environmental_impact_report_prepared", "nod_negative_declaration_prepared", "nod_other_document_type", "nod_mitigation_measures", "nod_mitigation_reporting_or_monitoring_plan", "nod_statement_of_overriding_considerations_adopted", "nod_findings_made_pursuant", "nod_final_eir_available_location"]`
- Unknown columns: `["lead_agency_name", "lead_agency_title", "lead_agency_acronym", "document_title", "posted", "document_description", "document_portal_url", "contact_full_name", "contact_authority", "contact_job_title", "contact_email_address", "contact_address_1", "contact_address_2", "contact_city", "contact_state", "contact_zip_code", "contact_phone_number", "location_coordinates", "cities", "counties", "county_clerks", "location_cross_streets", "location_zip_code", "location_total_acres", "location_parcel_number", "location_state_highways", "location_waterways", "location_airports", "noc_has_non_late_comment", "noc_state_review_start_date", "noc_state_review_end_date", "noc_development_type", "noc_local_action", "noc_project_issues", "noc_public_review_start_date", "noc_public_review_end_date", "noe_exempt_status", "noe_exempt_citation", "noe_reasons_for_exemption", "nod_agency", "nod_approved_by_lead_agency", "nod_approved_date", "nod_significant_environmental_impact", "nod_environmental_impact_report_prepared", "nod_negative_declaration_prepared", "nod_other_document_type", "nod_mitigation_measures", "nod_mitigation_reporting_or_monitoring_plan", "nod_statement_of_overriding_considerations_adopted", "nod_findings_made_pursuant", "nod_final_eir_available_location"]`
- Inspection digest: `e6888864835947ef758b22b5c3f8533fafa848a310e9b54acc94fd45fd5add07`
- Replay digest: `49d3aaf3357f448252ab8133e83bdfdb65175b0fe4646babfc0cc10af27f9b60`

## Independent verification

- Passed: `true`
- Finding count: `0`
- Findings: `[]`

## Maturity decision

CEQAnet remains `partial`. The successful offline replay proves that the one retained HTTP 200 response is structurally valid source-provided CSV when decoded as Windows-1252. It does not itself authorize promotion, another request, recurring operation, persistence, or broader coverage claims.

## Next gate

Review the successful point-in-time CSV proof and replay in a separate controlled source-maturity phase. Any promotion must bind both the original execution and replay digests and preserve the HTML 403 limitation as surface-specific evidence.

## Evidence artifacts

- `evidence/source_verification/ceqanet_csv_live_execution_2026-07-12.json`
- `evidence/source_verification/ceqanet_csv_windows1252_replay_2026-07-12.json`
- `evidence/source_verification/ceqanet_csv_windows1252_replay_verification_2026-07-12.json`
