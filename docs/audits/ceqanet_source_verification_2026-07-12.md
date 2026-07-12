# CEQAnet Source Verification Review — 2026-07-12

## Conclusion

CEQAnet is classified **partial**, not `verified`.

The public portal, search surface, recent-posting list, project-summary pages, individual document-detail pages, policy pages, and official CSV links were observed through ordinary browser access. A bounded automated collector later received HTTP 403. ConstructionSight did not disguise the client, bypass the response, download attachments, mutate persistence, or send outreach.

The most functional safe path is therefore:

1. preserve CEQAnet as a materially evidenced source;
2. expose its maturity as `partial` to operators;
3. keep recurring execution blocked behind the existing `verified` gate; and
4. prioritize an official CSV-based ingestion path or source-specific access clarification.

## Browser-observed public surfaces

- Public entry: `https://ceqanet.opr.ca.gov/`
- Observed redirect destination: `https://ceqanet.lci.ca.gov/`
- Advanced search: `https://ceqanet.lci.ca.gov/Search/Advanced`
- Recent postings: `https://ceqanet.lci.ca.gov/Search/Recent`
- Project-summary example: `https://ceqanet.lci.ca.gov/Project/2026030377`
- Individual document-detail example: `https://ceqanet.lci.ca.gov/2026070311`

The document-detail example exposed the fields most useful to ConstructionSight, including SCH number, lead agency, document title and type, received date, contacts, location, parcel information, development type, and attachment metadata.

## Official CSV surfaces

CEQAnet exposes official CSV links from reviewed pages:

- Project export example: `https://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=2026030377`
- Document export example: `https://ceqanet.lci.ca.gov/Search?DocumentId=1&OutputFormat=CSV&Sch=2026070311`

These links were observed but not downloaded in this phase. They are the preferred next integration target because they are explicit source-provided export surfaces and avoid brittle HTML-only extraction.

## Policy review

The following official pages were reviewed:

- `https://ceqanet.lci.ca.gov/Home/ConditionsOfUse`
- `https://ceqanet.lci.ca.gov/Home/Privacy`
- `https://ceqanet.lci.ca.gov/Home/Accessibility`

The Conditions of Use describe the site as a public service, discuss ordinary browsing and downloading, state that information is generally public domain unless otherwise indicated, and prohibit unauthorized modification, security circumvention, and use outside intended purposes. The reviewed pages do not provide an explicit recurring-automation authorization.

ConstructionSight therefore permits ordinary public review and source-provided exports but does not infer permission to defeat an HTTP 403 or other access control.

## Automated collection diagnostics

Three bounded GitHub Actions attempts produced the following evidence:

| Workflow run | Finding |
|---|---|
| `29182194949` | The original collector used brittle detail-page wording and rejected a valid page shape. |
| `29182315544` | Detail-page identity validation passed; `robots.txt` returned HTTP 406 under the collector request headers. |
| `29182383903` | The public entry returned HTTP 403 to the automated collector. |

Each run failed before repository mutation. No bypass was attempted.

## Registry effect

The CEQAnet registry row is changed from `unverified` to `partial` with a checked date of `2026-07-12`.

This status means:

- the source is real and materially observed;
- its public data model is useful to ConstructionSight;
- official export surfaces exist;
- automated recurring access is not yet approved or reliable; and
- `verified` promotion remains blocked.

## Remaining entry condition

Before `verified` promotion, ConstructionSight must complete one of the following under a separate governed phase:

- implement and validate bounded ingestion through an official CSV export contract;
- obtain source-specific clarification supporting the proposed automated access pattern; or
- establish another official machine-readable interface with preserved provenance and access constraints.

The existing recurring-run service must continue to reject `partial` sources.
