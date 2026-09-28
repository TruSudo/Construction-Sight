# ConstructionSight Full Branch Reconciliation Manifest

Created: 2026-09-28

## Purpose

This manifest is the durable starting inventory for the full ConstructionSight reconciliation campaign. No historical branch should be deleted until its functionality has been classified and either retained in the canonical integration line, explicitly superseded by a newer implementation, or preserved solely as historical/audit evidence.

## Canonical baseline

- Current main at campaign start: `d3d586b4e66ffd5e49f6466d1c4ad40f94ca0029`
- Reconciliation branch: `integration/full-reconciliation-2026-09-28`
- Total remote branches inventoried: **165**

## Classification states

- **contained** — branch tip is already an ancestor of current canonical integration history.
- **superseded** — implementation has been replaced by a newer retained implementation.
- **reconcile** — contains functionality/evidence that must be ported forward.
- **reconciled** — useful functionality has been ported forward into the canonical reconciliation line.
- **audit-only** — CI, certification, evidence, or historical branch not intended as product functionality.
- **archive** — preserve exact tip for history, but do not integrate into runtime.
- **pending** — not yet classified.

## Branch inventory

| Branch | Tip SHA | Status |
|---|---|---|
| `agent/add-arcgis-live-rehearsal-authorization` | `679f15fa6d39f222c16b8c5c3e99db7662465909` | contained |
| `agent/add-arcgis-proof-bundle-persistence` | `3a75e52b4e9dc72f263800c0aea4e862713fc70c` | superseded |
| `agent/add-arcgis-rehearsal-http-adapter` | `9b39f7822f22a319ae2c87324a33dd0345f663c1` | superseded |
| `agent/add-arcgis-rehearsal-proof-bundle` | `a0214f907e9afe2a0ec0db636727a74f6efd6c4c` | superseded |
| `agent/add-parcel-arcgis-acquisition-gates` | `00ffa2cbbd2fdafca6719ea1f1af298cf2f3f716` | superseded |
| `agent/assurance-context-provenance-hardening` | `511d51cd18c3bed599b29c7ce4fc07a10c1e311d` | pending |
| `agent/ceqanet-csv-access-policy` | `919aaf94750d1346b994f0f2797844461fbd3d48` | pending |
| `agent/ceqanet-csv-evidence-observation-1` | `ec2fd30069f25ddb526150069e67e2477ed958c2` | pending |
| `agent/ceqanet-csv-evidence-series` | `7d1b83042fedf8759f8295d034a821d22b6b5095` | pending |
| `agent/ceqanet-csv-export-contract-v2` | `7ef56c9ac329666d2d496321138eafe8c10fb350` | pending |
| `agent/ceqanet-evidence-repair-partial-v2` | `a2bf6eeb59157e1a8fa09e68217bf070d4cbe958` | pending |
| `agent/ceqanet-ingestion-dashboard` | `f3de9d5859261f97685e9debe33269d545dd6774` | pending |
| `agent/ceqanet-ingestion-dashboard-v2` | `c00e012075a7c5b1a2c41ce52c277c824adf3161` | pending |
| `agent/ceqanet-listing-to-exact-capture-queue` | `10c3dc87d8ab3cd519f60c97320285a4b860c0b5` | pending |
| `agent/ceqanet-live-csv-evidence-v4` | `33e92e3bc0315fb2835abfe593ac91b44a40ac6f` | pending |
| `agent/ceqanet-live-csv-proof-v3` | `421083a81b55f5e5294dd2f04016a12459cdaf76` | pending |
| `agent/ceqanet-official-csv-contract` | `ac5962209d46daacf88db8b50a2b77b05b373d81` | pending |
| `agent/ceqanet-queue-to-capture-provenance` | `5feae0a6e46300f7d7fb27e7ad3147d1e7d5c444` | pending |
| `agent/ceqanet-recurring-run-governance` | `f654f907ce4a886325e73f119fb95161ed86e8f0` | pending |
| `agent/ceqanet-source-maturity-proposal` | `26eb294bfcf5efbc598b093366307f84cde94603` | pending |
| `agent/ceqanet-source-verification` | `05cbd23fb414d3786c3e4a70370eeb6c38365c7d` | pending |
| `agent/ceqanet-windows1252-replay-v5` | `7faa3c208190ed07e00070b762dda0a93fe573e9` | pending |
| `agent/certification-grade-full-repo-audit` | `08409bd34d2706d50c1987c0aef566faaba4a8d7` | pending |
| `agent/command-center-capture-queue` | `8f63e6dbb2513bf1ee28427fff6350d965fb1945` | reconciled |
| `agent/command-center-evidence-navigation` | `16ef29d6b28d232f5760d4e7a7c171eec1819e06` | pending |
| `agent/command-center-filter-watchlist-navigation` | `f8c46f46ffbd1633c69b50f2cfcd1af96b5431c6` | pending |
| `agent/command-center-source-registry` | `de19f04410f84d97209ea44e3aa387b71c4db489` | reconciled |
| `agent/command-center-source-verification` | `b1ffdc66027720e8040a1aafa1d3729ec4a72689` | reconciled |
| `agent/explicit-source-attribution-aliases` | `1e78fda40bceed4a97b13e385433768e6c40f013` | reconciled |
| `agent/fix-ceqanet-windows1252-ruff` | `af2b48b61dc554f6150f5e10baa4b4fac22de291` | pending |
| `agent/governed-ceqanet-capture-preview` | `8477d0e9e7dfffbaaeb62a29e562e2b496a8f11b` | pending |
| `agent/harden-arcgis-bulk-rehearsal-proof` | `12770cb2b311e8c3bff40ca51ca81efc1da00bc4` | superseded |
| `agent/implement-arcgis-complete-rehearsal-executor` | `b40ff141511eb805a99cf6e81a15afc626c308ca` | superseded |
| `agent/lead-operator-cli` | `a5b25a00a43411992e645e405715fb500a1de8c9` | pending |
| `agent/mutation-witness-validation` | `8435b1de35f6ffab70ec2ba74e2c6a4b95102370` | pending |
| `agent/native-assurance-remediation` | `3e11e277cc1c5e0bc9d684498759d40f974b0753` | pending |
| `agent/native-assurance-remediation-076-096` | `10037faa8fb37d61e86b1b9a690fc09d33443e0a` | pending |
| `agent/operational-integration-gui` | `380e19c42acf3d82e7d2034de8940f2a7275b38a` | pending |
| `agent/record-county-arcgis-bounded-proofs` | `0a9559c86430ad4160f3ecdf6d0a118b8c808baf` | superseded |
| `agent/repair-ceqanet-evidence-partial` | `ec805fdf41fc474d1021f46bf00570e58b365123` | pending |
| `agent/result-authority-operator` | `a876d33d030033c18c538389f11c393b4f99846b` | contained |
| `agent/result-ledger-authority` | `3eda596c7da928f0502d0bfd9dc858f91a7356dd` | pending |
| `agent/result-ledger-correction-action` | `f96737884cc150396fcfc6cc210d41dc62ef4521` | contained |
| `agent/result-ledger-supersession` | `053b0099808bac770718a9f04328dcce1f898064` | pending |
| `agent/result-ledger-supersession-v2` | `d7e612c240f1bc44ac83af0805f430e1b6f65041` | contained |
| `agent/silent-risk-certification` | `fa756e75cced218411cbf2d5d4c973add9d9c196` | pending |
| `agent/source-attribution-coverage` | `2d98826dd224545be2112c185612a41c25718bc4` | reconciled |
| `agent/source-registry-controlled-apply` | `f45e399b18d86f34be974c437d81b1d3d16cffd5` | pending |
| `agent/test-drive-source-inventory` | `bb6c3ed1842d914b0fc28695626925f5865be21a` | reconciled |
| `agent/top-head-quality-and-ops` | `f80bfe5b207bc0467664ec66ef6db300c5e90c47` | pending |
| `agent/topology-grade-parcel-containment` | `b199455897feaf1cfcbf48992f525d941afe0b8a` | contained |
| `agent/ui-lock-command-center` | `4f74d875f8b7c14eb659c0c89941bc1eb261ff9d` | pending |
| `agent/upstream-operator-cli` | `a64ace077b00dcd3cff085858bc9a20db402aafa` | pending |
| `agent/verify-county-parcel-sources` | `6b259d743b38584d922ab9748b22dd4154016c1b` | pending |
| `agent/wkt-area-weighted-geometry` | `dac9459e7012fb3289fdca443d0807dcad549a65` | contained |
| `archive/silent-risk-e47e335` | `e47e33514ef906244d1f5959af49cc193b271305` | pending |
| `archive/silent-risk-e49cca5` | `e49cca5b557bf5d2b4e34513eae8fee83ab4734a` | pending |
| `assurance/close-assurance-supplychain-batch` | `2305fb3f5bd9a01d64c36451b6eeaf8d063179fc` | pending |
| `assurance/close-ci-supply-chain-batch` | `043ec23e23b65f3834fccea07e2a45008841ad1c` | pending |
| `assurance/close-cs-sr-026` | `41259ee8376b910fa038848832e2863900f0578a` | pending |
| `assurance/close-cs-sr-045` | `c8482d7e8382b023fdb7f1ebea04df50ad574fef` | pending |
| `assurance/close-cs-sr-048` | `15aff77d95361935c8b5244d259733aa32960f7c` | pending |
| `assurance/close-cs-sr-049` | `175b55de1fff99c7349668c19aab0bc54adc7178` | pending |
| `assurance/close-cs-sr-052-056` | `74598ce80a57c02c87e2d5cde68d3bd172d4bca0` | pending |
| `assurance/close-foundational-governance-batch` | `f773c926168c6284c171bfe05aac7f729c870ddc` | pending |
| `assurance/close-quality-regressions-065-067-070` | `9142ad5701c69006ef8cc3f7ad5e611d514d4e97` | pending |
| `assurance/close-transport-authorization-batch` | `7456e0f9820f2af219f1ac7bc0b5deba5746ca5f` | pending |
| `assurance/consolidation-defect-triage-2026-09-24` | `45f444ae3b6a187f992fb86d9d857397996e9f79` | pending |
| `assurance/fix-cs-sr-026-incremental-closure` | `53845f5bfa0d9b9c312de49eadfd7aae0178e8d9` | pending |
| `assurance/fix-cs-sr-045-lawful-access-facts` | `e8fb0753be361bf909405cd0f452164e8912c817` | pending |
| `assurance/freeze-6e568d2-resolution-map` | `af6b4c50c23a62d4e70d761e6970843c4f199a14` | pending |
| `assurance/native-assurance-base-539939a` | `539939a8cdef813b919b1c725fa1439d03d97ea7` | pending |
| `assurance/permanent-resolution-integration` | `ce0afda095cf03407f9b65d533d93eae2054f317` | pending |
| `audit/pre-remediation-baseline-2026-08-21` | `5f101b7bdddfd695904eb02144350e06207d9ded` | pending |
| `cleanup/coverage-report` | `39d4492070f5690c3264fb4d692720119fe5f5bc` | pending |
| `cleanup/doctrine-runtime-sync` | `96b43d9c265317df4e83937737a4d4c880a64874` | pending |
| `cleanup/geometry-hardening` | `10028eeb0dd3dd4722a77f0c52aabe017de7c1c2` | pending |
| `cleanup/lead-status-rules` | `18285939c2935f28537a0901f6701f55b92dbd0e` | pending |
| `cleanup/ledger-rules` | `39d4492070f5690c3264fb4d692720119fe5f5bc` | pending |
| `cleanup/ledger-share-state` | `400d9744a4f4483668494d8dc3ec2b36eec9ee38` | pending |
| `cleanup/persist-lead-workflow-records` | `8825371051020d3badbbc9f59a594702a29ffba7` | pending |
| `cleanup/persist-movement-identity` | `017c03e15bfcfdae22f7ec2ade69a6a85d8d9edb` | pending |
| `cleanup/persist-parcel-site-records` | `1651e3f55e93acdf88d07bb846dd05ad3e1ffbfa` | pending |
| `cleanup/post-70-doc-sync` | `e67907ada5d12eb1f1dcc2e93b8f37c9d2fca4a9` | pending |
| `cleanup/post-72-audit-refresh` | `3d4d81160c8b1113c6a32041ebf12f8da4bd986e` | pending |
| `cleanup/post-75-audit-package-reconciliation` | `ec904b55cca0f665959e9569f91c06f2ca4c2c98` | pending |
| `cleanup/post-80-source-plan-reconciliation` | `b26e6ef17e1b2ff0bc840bfea5dc17c2ba72ae3f` | pending |
| `cleanup/source-observation-template` | `1987dda64b8bcf04f79e83948fd6867a73d1f400` | pending |
| `cleanup/source-plan-apply-output` | `2ff3faf21333edc7c25037867818fe34af8a536e` | pending |
| `cleanup/source-promotion-plan` | `8c50ed7cda5bd188af2bbf38d88c46a200c5bcf4` | pending |
| `cleanup/source-readiness-workflow` | `3c486ac54f61a0fffc3f808d170d4275951cd7af` | pending |
| `cleanup/source-registry-update-plan` | `166aa350e6c6fd02e3ae3a440e3ad0c51ffe2f77` | pending |
| `cleanup/source-report-docs` | `806c361ed528be195caaaa1df04c71ef871f6c34` | pending |
| `cleanup/source-status` | `4077c874a299d06530e4f67af63ad099aeaf03cc` | pending |
| `cleanup/source-status-command-shape` | `f782877898dcc81604372f348c9476603d5aac20` | pending |
| `cleanup/source-verification-checklist` | `12063ce8d902758c32c0eb7493325b5f0d307685` | pending |
| `cleanup/storage-coverage-matrix` | `8a95f66f0ebafee899c6e0c67df53afca1669e0b` | pending |
| `cleanup/storage-summary-cli` | `90a200531b79250ef597a0c56dbfc089c2141042` | pending |
| `cleanup/verification-report` | `6236a9e8b8e06bac94239f52042a195b0adc86ba` | pending |
| `cleanup/versioned-scoring-profile` | `181eaeb840fec189d5a646270f6f07bcdc6b12f5` | pending |
| `codex/parcel-longitudinal-evidence` | `2421fe52cf6b9e30db14b499b61084daec81c149` | pending |
| `feature/artifact-resolution-examples` | `297ded6b64d753ed82365151a2c50dfef9558617` | pending |
| `feature/artifact-resolution-examples-clean` | `60a152dc2b43a01699ab298ba5ae2b0a7258d0e7` | pending |
| `feature/ceqanet-chain-report-cli` | `494a088e10900e90da4017c11f894ffee79c746d` | pending |
| `feature/ceqanet-detail-enrichment` | `5e63ad787a03acb17686828dc7d55d866385ab69` | pending |
| `feature/ceqanet-detail-enrichment-cli` | `d2734152fd40c7b7a04b4059de59d39f8914940e` | pending |
| `feature/ceqanet-detail-execute-cli` | `38c3ea56f2e275ee3a4d5a5f5793b853fbb912d3` | pending |
| `feature/ceqanet-fixture-query` | `43d52c91dc73611c66c56c17562bc281fae7943c` | pending |
| `feature/ceqanet-fixture-query-cli` | `4f045dc7151ddb5c6769c5152d991c98c25502a5` | pending |
| `feature/ceqanet-listing-dry-run` | `76181acda6534956a3fbff3fe852310a257dc7f5` | pending |
| `feature/ceqanet-listing-dry-run-cli` | `4a7fa0f170a21948870521f684545ac2f1703747` | pending |
| `feature/ceqanet-listing-execute-cli` | `105f93bd5f564bbea545b0f4777dddf9e902ca6f` | pending |
| `feature/ceqanet-listing-live-executor-contract` | `f1ebe4a5df2a55f6a11634b545579baa533b9b76` | pending |
| `feature/ceqanet-listing-plan-cli` | `147ba2e28017fde6afd3c72d73d5c36585756bc2` | pending |
| `feature/ceqanet-operator-archive` | `8c064c7cc534ab2e745289878dac8b666da20a18` | pending |
| `feature/ceqanet-operator-archive-verify` | `46a034b73eae05f31885217ea932f691c086e2e4` | pending |
| `feature/ceqanet-operator-bundle` | `f94ea82ef1434e4c419d1bd0e3414f1c45bbffef` | pending |
| `feature/ceqanet-operator-bundle-components` | `b7a4c30432af0d480bf7f82e2e869e10fa0bd03e` | pending |
| `feature/ceqanet-operator-bundle-verify` | `4388a24d8748fcd2f4ca8991eacffbc7a8038748` | pending |
| `feature/ceqanet-operator-export` | `d61198bed7d479da228aab2b8f261853c44a624a` | pending |
| `feature/ceqanet-operator-package` | `1d33f60c32d39b27788967181b9528cbd55bb1e0` | pending |
| `feature/ceqanet-operator-report` | `629732dc66bdd94992fe1c834e452112311e9afc` | pending |
| `feature/ceqanet-persistence-execution` | `17e2e43266898e1efa3526cd7d3b6a3fd2fe2720` | pending |
| `feature/ceqanet-persistence-preview` | `4a248a59f09616908dffa7017596fd4330eb0363` | pending |
| `feature/ceqanet-readonly-listing-plan` | `e060713ee33634a4f1f3a4df81e09e17ead5499e` | pending |
| `feature/ceqanet-write-plan-preview` | `232e444466bb85e8094be6840f0c36210dd39881` | pending |
| `feature/contractor-identity-spine` | `5f466ac07e09955e4cfdabceb1918075e7a2de51` | contained |
| `feature/decision-record-spine` | `4c7773724a53ee72988ad67b60633fc7219379f6` | contained |
| `feature/external-intelligence-capability-spine` | `8940dec62074ce5b9dd98a1cb55f3fdcd15b3d61` | contained |
| `feature/external-intelligence-capability-spine-main-ci` | `8940dec62074ce5b9dd98a1cb55f3fdcd15b3d61` | contained |
| `feature/lead-duplicate-suppression` | `eeaa87f401486c8ed4d98cdfc5599467a767b149` | contained |
| `feature/lead-workflow-status-spine` | `ebcee77172338ebe53f755b237fed4c5d06c0445` | contained |
| `feature/opportunity-action-package` | `b01a00537777dc962d1e8831aa27451e0e05c6eb` | contained |
| `feature/opportunity-enrichment-spine` | `f673925e6a46cdde8a49fe1985fe35570a25ea0c` | contained |
| `feature/opportunity-transition-intake` | `67723569fb0b560995d04e80279c48790fe705a1` | pending |
| `feature/parcel-fact-assurance` | `7643bfbf8216ca2b00d84937130b5f782250d79d` | pending |
| `feature/parcel-import-preview` | `0317f84a9276eb5d668a9b72949fdd019904ba02` | pending |
| `feature/parcel-record-geometry-normalization` | `1e1ae6d194b3f88250a59164e30fe462c593c90b` | pending |
| `feature/parcel-site-resolution-spine` | `4c6d1496a034c801815adcb9bd5761f129e14961` | contained |
| `feature/parcel-source-registry` | `0b7d986d2416b7dbf2a7168ce238e7808b3133e5` | pending |
| `feature/parcel-source-schema-preview` | `8c7413a43fce89a2515c25b1d2d5b0b7fa6bd687` | pending |
| `feature/permit-snapshot-transition-spine` | `4607b5b74100d8499d123dc1a3cdda3a82d297aa` | contained |
| `feature/repo-wide-ruff-baseline-cleanup` | `5366428ea2964c3305a4477ce3ef8f476430de3a` | pending |
| `feature/result-ledger` | `d090f0740ffb052ccf61c0d296cc01357e0a2ad8` | pending |
| `feature/shovels-regrid-gap-alignment` | `19344349f54d994f5e8481efa8c866ac65f04889` | contained |
| `feature/site-resolution-parcel-enrichment` | `018d268b23fa79964fc10886369e52ac822d48e9` | pending |
| `feature/universal-intake-spine` | `0cfb641b8f444075e3a1a4231a89c0da8b31173a` | pending |
| `fix/cs-sr-045-lawful-access-facts` | `42642d460ec7b9ad44183e0e3a4f8662afa089b7` | pending |
| `fix/cs-sr-046-epistemic-provenance` | `3b8c333636c56b0113f4bee36b74367bc8f7ee75` | pending |
| `integration/constructionsight-baseline-2026-09-24` | `6e568d2c266550be14f50f1270f4a5d13889d787` | contained |
| `integration/freeze-6e568d2-2026-09-25` | `6e568d2c266550be14f50f1270f4a5d13889d787` | contained |
| `integration/reconcile-source-inventory-2026-09-24` | `4dbd1a4bd8b36fa7af27aab65b19bcfbfbabc548` | reconciled |
| `main` | `d3d586b4e66ffd5e49f6466d1c4ad40f94ca0029` | pending |
| `noop` | `b601bf7caca9f0efc9bfea885f5b18ae556bed1f` | pending |
| `noop2` | `db183c03d12993812af573e3ea66ca0f174ddfcc` | pending |
| `release/integrated-baseline-2026-09-24` | `891679d9ca2cb1262faa2da67460ba9c47f29296` | contained |
| `remediation/closure-certification-sync` | `f1a777ba9b4b20bf5eb53ab1d17a35c50e2eca08` | pending |
| `remediation/confidence-test-fixtures` | `eb07760e8de6aa45d3001ae1a7e374f09cba0434` | pending |
| `remediation/cs-sr-048-current-line` | `13e4ebf9befbac90154110b315e855ba6b2d31dd` | pending |
| `remediation/cs-sr-053-fixed-decimal` | `7456e0f9820f2af219f1ac7bc0b5deba5746ca5f` | pending |
| `remediation/cs-sr-053-fixed-decimal-v2` | `7b4782b212da4fa3490ce9688b404b41015fd6a4` | pending |
| `remediation/operational-confidence-gating` | `b555632e1d91faf1a7a64be3ecebd765f83bd0c6` | pending |
| `remediation/result-ledger-content-and-money` | `de1007dd04300b521b1b6ad5713b98ab82b11ddc` | pending |
| `remediation/schema-version-governance` | `1866453b6cfcf63b6c0cd2af4cbb234daa59581f` | pending |
| `remediation/test-governance-sync-batch` | `eb07760e8de6aa45d3001ae1a7e374f09cba0434` | pending |

## Non-negotiable reconciliation rules

1. Delete nothing until all branches are classified.
2. Do not blindly merge stale/diverged branches into current main.
3. Preserve functionality, behavior, evidence, and provenance—not obsolete implementation accidents.
4. Port missing functionality into the current hardened architecture.
5. Record the destination commit/file for every reconciled lineage.
6. Run focused tests after each subsystem and the full quality suite before merging the reconciliation line to main.
7. Keep Git history and original branch tip SHAs as the recovery map throughout the campaign.
