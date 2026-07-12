"""Reconcile PR #98 runtime with canonical status documentation."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one documentation anchor in {path}, found {count}: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_readme() -> None:
    path = ROOT / "README.md"
    replace_once(
        path,
        "ConstructionSight now has an offline official CSV contract that can plan exact project/document export URLs and validate already-obtained CSV bytes. It does not fetch the URL or change source maturity. The next source step is a separately authorized bounded live CSV proof or source-specific access clarification, followed by a separate controlled promotion to `verified` only if the evidence supports it.",
        "ConstructionSight now has an official CSV contract that can plan exact project/document export URLs, validate already-obtained CSV bytes, and perform one explicitly authorized bounded GET with no retry. The live-proof boundary retains the complete response envelope and canonical offline inspection but has not yet produced a committed live proof. Source maturity therefore remains `partial`; promotion remains a separate controlled decision supported only by reviewed evidence.",
    )
    replace_once(
        path,
        "The official CSV boundary is offline-only:\n\n```text\n10-digit SCH number + optional document ID\n  -> exact official CSV URL identity\n  -> already-obtained CSV bytes\n  -> content-type, encoding, header, row, and SCH validation\n  -> body hash + bounded normalized rows + inspection digest\n```\n\nThe CSV boundary authorizes neither a network request nor persistence mutation.",
        "The official CSV boundary has separate offline and one-request proof layers:\n\n```text\n10-digit SCH number + optional document ID\n  -> exact official CSV URL identity\n  -> either already-obtained CSV bytes\n     or explicit one-GET/no-retry live authorization\n  -> complete response-envelope retention\n  -> content-type, encoding, header, row, and SCH validation\n  -> body hash + bounded normalized rows + inspection digest\n  -> independent offline execution verification\n```\n\nPlanning, local inspection, and execution verification are offline. Live proof requires explicit authorization for one request and never authorizes attachment download, persistence mutation, retries, or scheduling.",
    )
    replace_once(
        path,
        "- Offline CSV media-type, UTF-8/BOM, schema, row-width, SCH, and digest validation\n- Preservation of original, normalized, canonical-role, and unknown CSV columns\n",
        "- Offline CSV media-type, UTF-8/BOM, schema, row-width, SCH, and digest validation\n- One-request CEQAnet CSV live-proof execution with explicit authorization and no retries\n- Complete response-byte, URL, status, header, body-hash, and inspection evidence\n- Independent offline verification of the retained live execution envelope\n- Preservation of original, normalized, canonical-role, and unknown CSV columns\n",
    )
    replace_once(
        path,
        "- The official CSV contract is offline-only; it has not performed or authorized a live export request.\n- Real CEQAnet CSV column drift remains unknown until a source-provided body is obtained and inspected.\n",
        "- The official CSV contract can perform one explicitly authorized proof request, but no live proof artifact has yet been committed or reviewed.\n- Real CEQAnet CSV availability and column drift remain unknown until a source-provided response is retained and passes the canonical inspection.\n",
    )


def patch_status() -> None:
    path = ROOT / "docs/architecture/current_implementation_status.md"
    replace_once(
        path,
        "| CEQAnet official CSV contract | Yes | Yes | Yes | Artifact-only | Yes | No | Exact official project/document URL identities and already-obtained CSV bodies can be validated offline with body hashes, schema checks, SCH agreement, unknown-field preservation, bounded rows, and inspection digests. No network or persistence is authorized. |",
        "| CEQAnet official CSV contract | Yes | Yes | Yes | Artifact-only | Yes | Guarded proof only | Exact official URL identities and offline body inspection remain canonical. A one-request/no-retry live-proof boundary now retains complete response evidence and independently verifies canonical inspection agreement. No live proof artifact, persistence, scheduling, or source promotion is claimed. |",
    )
    replace_once(
        path,
        "| CS-PLAN-002 | Verified recurring live adapters | CEQAnet has browser-reviewed public surfaces, `partial` maturity, verified-only recurring-run governance, and an offline official CSV URL/body contract. Automated HTML collection received HTTP 403 and remains blocked; no scheduler exists. | Perform one separately authorized bounded official CSV proof, preserve response evidence, pass the offline contract, then complete controlled `verified` promotion before attempt-ledger, scheduling, retry, archive, observability, and downstream handoff work. |",
        "| CS-PLAN-002 | Verified recurring live adapters | CEQAnet has `partial` maturity, verified-only recurring-run governance, an offline official CSV inspector, and a one-request/no-retry live-proof boundary. Automated HTML collection received HTTP 403 and remains blocked; no live CSV proof or scheduler exists. | Execute one self-removing bounded project CSV proof, preserve and verify the complete response artifact, then make a separate controlled maturity decision before attempt-ledger, scheduling, archive, observability, and downstream handoff work. |",
    )


def patch_audit() -> None:
    path = ROOT / "docs/audits/full_repo_audit_inventory.md"
    replace_once(
        path,
        "- an offline source-provided CEQAnet CSV URL/body contract with digest-bound inspection;",
        "- a source-provided CEQAnet CSV URL/body contract with offline inspection and a one-request/no-retry live-proof envelope;",
    )
    replace_once(
        path,
        "ConstructionSight is not yet a production recurring live-source platform. Most adapter families are contracts or planned integrations. CEQAnet is canonically `partial`: its official public pages, policies, data fields, and CSV links are materially observed, but bounded automated HTML collection received HTTP 403 and no bypass was attempted. The offline CSV contract performs no network request and proves no live availability. The other three canonical sources remain unverified. No source is currently `verified`, no production scheduler exists, and no external outreach-sending behavior or GUI/operator application is implemented.",
        "ConstructionSight is not yet a production recurring live-source platform. Most adapter families are contracts or planned integrations. CEQAnet is canonically `partial`: its official public pages, policies, data fields, and CSV links are materially observed, but bounded automated HTML collection received HTTP 403 and no bypass was attempted. The CSV contract now supports exact offline inspection and one explicitly authorized proof request, but no live proof artifact has been committed or reviewed. The other three canonical sources remain unverified. No source is currently `verified`, no production scheduler exists, and no external outreach-sending behavior or GUI/operator application is implemented.",
    )
    replace_once(
        path,
        "| CEQAnet official CSV contract | Yes | Yes | Yes | Artifact-only | Yes | No | Exact project/document export URLs and already-obtained CSV bodies are validated offline. Body size/hash, media type, encoding, headers, canonical roles, row width, SCH agreement, retained rows, unknown columns, and inspection digest are preserved. |",
        "| CEQAnet official CSV contract | Yes | Yes | Yes | Artifact-only | Yes | Guarded proof only | Exact URL planning and offline inspection remain canonical. One explicit GET with no retry may retain the complete response envelope, embed canonical inspection, and produce an independently verifiable execution digest. No live proof artifact or persistence is claimed. |",
    )
    replace_once(
        path,
        "| CS-PLAN-002 | Verified recurring live source adapters | CEQAnet is `partial`, official public pages and CSV links are documented, verified-only recurring-run governance exists, and an offline official CSV URL/body contract is implemented. Automated HTML collection received HTTP 403; attempts are not scheduled or persisted as a ledger. | Perform one separately authorized bounded official CSV proof, preserve response evidence, pass the offline contract, then complete controlled `verified` promotion before attempt identity, scheduling, retry, archive, observability, and downstream handoff work. |",
        "| CS-PLAN-002 | Verified recurring live source adapters | CEQAnet is `partial`, verified-only recurring-run governance exists, and the CSV surface has offline inspection plus a one-request/no-retry proof boundary. Automated HTML collection received HTTP 403; no CSV proof, attempt ledger, or scheduler exists. | Execute one self-removing bounded project CSV proof, preserve and verify its complete response evidence, then make a separate controlled maturity decision before attempt identity, scheduling, archive, observability, and downstream handoff work. |",
    )
    replace_once(
        path,
        "| Official CSV contract | Deterministic URL planning and already-obtained body inspection exist offline; no live proof is claimed. |",
        "| Official CSV contract | Deterministic URL planning, offline inspection, and one-request/no-retry proof execution exist; no live proof artifact is yet claimed. |",
    )
    replace_once(
        path,
        "| CEQAnet CSV inspections | Schema-versioned JSON artifacts may be written by the operator CLI; the contract performs no database write or source fetch. |",
        "| CEQAnet CSV inspections/executions | Schema-versioned offline inspections and live-proof execution envelopes may be written by the operator CLI; no database write, attachment download, retry, or schedule is authorized. |",
    )
    replace_once(
        path,
        "| CEQAnet official CSV contract | `plan` and `inspect-file` commands emit exact-schema JSON without network or persistence access. |",
        "| CEQAnet official CSV contract | `plan`, `inspect-file`, `execute-live`, and `verify-execution` expose offline planning/inspection, one explicit proof GET, and offline verification. |",
    )
    replace_once(
        path,
        "- exact CSV request URL/query identity, body length/hash, media type, encoding, headers, canonical roles, unknown columns, row counts, truncation, retained rows, and inspection digest;",
        "- exact CSV request/final URL identity, status, headers, complete response bytes, body length/hash, media type, encoding, canonical roles, unknown columns, row counts, truncation, retained rows, inspection digest, retry count, and live execution digest;",
    )


def main() -> None:
    patch_readme()
    patch_status()
    patch_audit()


if __name__ == "__main__":
    main()
