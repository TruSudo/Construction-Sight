# Fix-only campaign execution record — September 21, 2026

The [complete starting reconciliation](fix_only_reconciliation_2026-09-21.md) covers all 74 original defects. All remain active. CS-SR-075 additionally records confirmed lint and test-suppression failures: nine shared lint errors and one additional GUI import-order error. No Native Maximum Assurance pass, owner acceptance, release certification, or completed live-source collection is claimed.

## First correction batch: evidence readers and quality failures

Starting hardening head: `1a8f1b1e38e9f7ab11adcf629400fb4123c8ddf8`; starting GUI head: `a3392b8c1b7f44eb0c3c536b737bdae1420c646f`. Both were re-fetched before preparing branch updates. PR #117 remains based on main; PR #119 remains stacked on PR #117. Only those development branches are authorized for updates.

Reproduced before correction:

- CEQAnet bundle verification followed a symlinked ancestor, opened an outside artifact during a parent-directory swap before later rejecting it, and accepted evidence when atomic no-follow support was unavailable. Three regressions failed before the shared reader was introduced.
- ArcGIS bounded-proof and ZIP loaders accepted both final-file and ancestor symlinks. ZIP entry limits were checked after the ZIP library had constructed its central-directory objects. Five additional regressions failed before integration corrections.
- Both exact starting CI runs failed actual lint and structural-preflight commands despite successful continue-on-error step conclusions. The GUI's tenth lint error was corrected after a second inspection of its retained logs.

Implemented:

- `storage/runtime_artifacts.py` opens every ancestor relative to a pinned directory descriptor, rejects symlinks and nonregular files, checks file and ancestor identity before returning success, bounds reads before and during materialization, and closes descriptors on rejection. Canonical references reject traversal, absolute names, alternate separators/streams, control characters and Windows filename aliases. Platforms lacking required atomic primitives reject evidence access before opening it; native Windows success is not established.
- CEQAnet bundle inspection and its export/archive consumers use the shared reader. ArcGIS bounded-proof disk loading is separated into `parcel_source_acquisition_bundle_io.py`, preserving the pure domain builder's architectural boundary. Portable rehearsal proof loading uses the same bounded reader.
- ZIP inspection reads a bounded immutable snapshot, checks both declared and independently counted central-directory entries before `ZipFile` construction, and applies a one-MiB directory ceiling. Split/ZIP64/inconsistent archive metadata fail closed. Existing decompressed-member and aggregate bounds remain enforced.
- Import ordering, nested context managers and loop-variable capture errors are corrected. The prohibited conditional skip is replaced with executable capability-rejection coverage. No lint rule, assertion, mutation requirement or certification requirement is disabled.
- Six new mutation witnesses cover ancestor no-follow access, inode identity, unavailable platform primitives, concurrent file growth, ZIP directory pre-materialization and ZIP verify-use byte binding.

## Verification retained for this batch

[Raw outputs and SHA-256 manifest](evidence/2026-09-21-reader-batch/manifest.json) preserve the eight starting CI job logs, before/after regressions and working-candidate diagnostics.

| Check | Result | Scope and limitation |
|---|---|---|
| Hardening full tests | 1,574 passed; warnings are errors | Local Python 3.12.14 candidate; 52 additional test cases |
| GUI full tests | 1,678 passed; warnings are errors | Integrated candidate before the final GUI import-order-only correction |
| Focused security mutation certification | 121/121 killed; zero invalid failures, survivors or timeouts | Hardening working candidate, including six added witnesses |
| Ruff | Passed on both branches | All production and test files |
| Strict mypy | Passed: 263 hardening / 273 GUI source files | Local environment |
| Structural preflight | Recheck on committed candidates required | The first working-tree run correctly rejected a dirty checkout and literal skip syntax in the new finding's explanatory TOML text. The explanation was reworded; the scanner was unchanged. |
| Native Maximum Assurance | Not performed | Requires complete remediation, five genuine isolated reviews, exact-candidate gates and owner acceptance |

The local environment is diagnostic, not the required hash-locked release environment. Python 3.11 is unavailable locally; the existing canonical GitHub CI matrix must qualify both supported runtimes. No exact-head CI claim for a new commit is made in this pre-publication record.

## Remaining implementation and review work

CS-SR-054 remains partially corrected. Remaining paths include retained ArcGIS response/checkpoint stores, other local evidence loaders and filesystem publication. Ancestor swaps during writes, create-only/replacement publication, cross-artifact recovery and native platform qualification still need complete corrections and evidence. CS-SR-055 retains additional intake/enumeration/JSON bounds work. CS-SR-058 and CS-SR-061 require actual filesystem effects and coupled success records to participate in the commit and consumption protocols.

The original reconciliation's unresolved source-access, provenance, identity, confidence, duplicate gating, ledger identity, monetary representation and schema-evolution findings remain execution work. No entry is moved to the resolved ledger by this batch.

Codex Security is installed and enabled, including after the user's usage reset and renewed selection, but no scan/review action is exposed to this session. This blocks that optional review resource, not the authorized implementation and test work. Five isolated assurance passes have not begun because the complete defect inventory is not yet remediated.

## First batch committed and verified on both supported runtimes

Hardening advanced without force to `008a1a29cf3dccbff2ecf3113c50777607fa33fb`, tree `3b7eb4801095f49f73de42dd07d011c1e7e91389`. The GUI advanced without force to two-parent merge `e0055d010a548477a9dd98809651f303e47e8411`, tree `97434f646cab03985104ac4693195bdb0da4ba98`, preserving its previous head and the new hardening head as parents. Both PR bodies were updated and both remained drafts.

The actual raw logs from [hardening CI 35589904486](https://github.com/TruSudo/Construction-Sight/actions/runs/35589904486) and [GUI CI 35589907069](https://github.com/TruSudo/Construction-Sight/actions/runs/35589907069) establish these results on each exact head:

| Gate | Hardening Python 3.11 / 3.12 | GUI Python 3.11 / 3.12 |
|---|---|---|
| Ruff | Passed / passed | Passed / passed |
| Strict mypy | Passed, 263 files / passed, 263 files | Passed, 273 files / passed, 273 files |
| Full warning-strict tests | 1,574 / 1,574 passed | 1,678 / 1,678 passed |
| Security mutation certification | 121/121 killed / 121/121 killed | 121/121 killed / 121/121 killed |
| Native structural preflight | Zero findings / zero findings | Zero findings / zero findings |
| Isolated vulnerability audit | Passed, zero active published advisories / passed, zero | Passed, zero active published advisories / passed, zero |
| Release certification | Blocked by 75 active defects and missing assurance | Blocked by 75 active defects and missing assurance |

The quality-job aggregate fails deliberately because release certification still has those 76 blockers. Actual gate outcomes were inspected in the logs; successful continue-on-error step conclusions were not used as proof. CS-SR-075's corrective mechanisms and required runtime/branch checks now have evidence, but its Native Maximum Assurance closure requirement remains unmet. No defect is closed.

## Second correction batch: ArcGIS publication, checkpoints and replay

The next batch begins from the exact committed heads above. Before changes, six retained-response tests reproduced temporary-name symlink writes, parent symlink and swap escapes, replacement of a racing conflict, and unsafe final/ancestor reads. Five checkpoint tests reproduced the same temporary-name/parent problems, unsafe reads and JSON materialization before any file ceiling. Portable-proof output followed a symlinked ancestor, and four portable artifact names containing Windows drive/stream/device/trailing-dot aliases passed their own field validator. Raw failing outputs are retained.

The shared writer now stages through a pinned, exclusively created private directory, bounds chunks before writing beyond the limit, fsyncs complete content, publishes through an atomic create-only link, verifies inode identity, and fsyncs the parent before reporting success. Cleanup uses pinned directory handles. Retained responses, checkpoints and portable proof bundles share this protocol. Checkpoint reads now enforce a 16-MiB ceiling before JSON parsing. Artifact receipts and embedded portable references use the same canonical-name validation.

Testing during implementation exposed an additional path within CS-SR-054's existing scope: a handled create-only conflict could skip the enclosing parent's final identity check. The check now runs even when the body raises. A regression rejects a substituted regular directory during exact replay. Successful replay validates through one held file descriptor and then syncs that file and its parent; conflicting content is rejected before that durability step.

Validation of the second working candidate: **1,601 hardening tests and 1,705 GUI tests passed**, with warnings treated as errors. Ruff and strict mypy passed on both trees. The six added mutation witnesses and the moved read-growth witness all failed as intended under the targeted mutation run (7/7 killed); the full contract now contains 127 cases and still requires complete exact-head CI qualification. Before/after outputs, the previous committed preflight results, and all eight first-batch CI logs are retained in the [publication-batch evidence manifest](evidence/2026-09-21-publication-batch/manifest.json).

The failure tests establish bounded writes, concurrent exact replay, create-only conflict preservation, descriptor cleanup, sync ordering, injected publication/sync failures and safe exact retry. They do not establish power-loss behavior on every native filesystem. A hard process termination may leave a private staging directory, and deterministic orphan cleanup and coupled multi-artifact recovery remain CS-SR-058 work. Other runtime loaders and CEQAnet/report/registry publication paths remain CS-SR-054/055/058 work. All 75 defects remain active, and the five-pass assurance campaign has not started.
