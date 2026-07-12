# CEQAnet Bounded Live CSV Proof

Executed at: `2026-07-12T07:20:53.708319+00:00`

## Approved request

- Method: `GET`
- Request URL: `https://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=2026030377`
- Final URL: `https://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=2026030377`
- SCH number: `2026030377`
- Retry count: `0`
- Explicit network execution: `true`

## Response evidence

- HTTP status: `200`
- Content type: `text/csv`
- Content disposition: `attachment; filename="CEQA Documents.csv"`
- Observed body bytes: `7832`
- Retained body bytes: `7832`
- Complete body retained: `true`
- Body SHA-256: `5b1bc503c81d12ed0f00e52539edb437b42ae4c3a539a25e1c82a02b84273163`
- Execution digest: `9a861dcee42092eb6f2d8f5c86673f4aca4c75cd0d42beddaa930cc093221a95`
- Document downloads: `false`
- Persistence mutated: `false`

## Canonical inspection

- Inspection present: `false`
- Row count: `None`
- Headers: `[]`
- Inspection error: `CEQAnet CSV body must use UTF-8 or UTF-8 with BOM`
- Inspection digest: `None`

## Independent verification

- Passed: `false`
- Finding count: `2`
- Findings:
  - live CSV offline inspection failed: CEQAnet CSV body must use UTF-8 or UTF-8 with BOM
  - live CSV inspection recorded error: CEQAnet CSV body must use UTF-8 or UTF-8 with BOM

## Maturity decision

CEQAnet remains `partial`. This one request does not itself change source maturity.

## Next gate

Add strict, explicitly identified Windows-1252 compatibility to the offline CSV parser and replay the already-retained response bytes. No second network request is required or authorized for that correction. Preserve the original failed execution and verification artifacts as historical evidence; any successful replay must be a separate derived artifact. Source promotion remains a later controlled decision.

## Evidence artifacts

- `evidence/source_verification/ceqanet_csv_live_execution_2026-07-12.json`
- `evidence/source_verification/ceqanet_csv_live_verification_2026-07-12.json`
