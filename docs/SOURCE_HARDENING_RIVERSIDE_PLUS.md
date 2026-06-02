# Source Hardening — Riverside County PLUS Online

## Issue

Phase 3 local validation showed Riverside County PLUS Online failed verification under the seed URL:

```text
https://www.rivcoplus.org/
```

Observed result:

```text
Reachable: false
Detected Platform: unknown
Search: false
Login: false
Confidence: 10
Status: failed
```

## Correction

The seed record was corrected to use:

```text
https://rivcoplus.org/
```

The source was also reclassified from:

```text
accela_aca
```

to:

```text
tyler_energov
```

because the non-`www` public URL redirects into an EnerGov SelfService path.

## Updated File

```text
data/source_registry.seed.json
```

## Follow-Up Validation

Run locally:

```bash
git pull origin main
rm -f data/constructionsight.sqlite3
constructionsight init-db
constructionsight load-sources data/source_registry.seed.json
constructionsight verify-sources --limit 2
constructionsight list-sources
```

Expected result:

- Riverside County PLUS Online should no longer fail because of the stale `www` URL.
- Detected platform should be `tyler_energov` if the public response exposes EnerGov/Tyler hints.
- If it remains partial, the result should document why lightweight verification cannot fully classify it.

## GitHub Issue

Tracked under issue #1.
