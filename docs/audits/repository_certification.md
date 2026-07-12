# Repository Certification Protocol

## Purpose

ConstructionSight repository certification is a blocking integrity gate, not a general statement that every planned product capability is implemented. Certification means the complete tracked repository tree is internally consistent and contains no known defect within its documented supported scope.

A planned feature is not a defect when all of the following are true:

- the capability is explicitly marked planned or absent;
- current runtime behavior does not imply that the capability exists;
- the absence cannot corrupt, overwrite, misclassify, or overstate supported results;
- an implemented guard prevents unsafe fallback or accidental use; and
- an entry condition is recorded before future implementation.

## Certification inputs

The certification command is:

```text
python -m constructionsight.repository_certification --root . --require-clean-worktree
```

The command enumerates the repository with `git ls-files`; it does not rely on GitHub code-search indexing, file-name assumptions, or a hand-maintained inventory.

## Tracked-tree checks

Certification rejects:

- case-insensitive or Unicode-normalization path collisions;
- tracked cache directories, bytecode, editor backups, temporary files, and diagnostic output;
- unexpectedly oversized tracked files;
- invalid UTF-8 text, carriage-return line endings, missing final newlines, and trailing whitespace;
- malformed Python, JSON, or TOML;
- lint, type-check, and coverage suppressions;
- skipped, conditionally skipped, or expected-failure tests;
- deferred-work markers in source and configuration files;
- non-abstract production functions that raise `NotImplementedError`;
- private-key material and common secret-token forms;
- broken relative Markdown links;
- missing or malformed console-script modules and target attributes;
- weakened Ruff or mypy configuration;
- missing mandatory CI gates; and
- a dirty worktree after validation.

## Mandatory CI matrix

Every pull request and push to `main` must run on Python 3.11 and Python 3.12 with:

```text
python -m pip check
python -m ruff check src tests
python -m mypy src
python -m compileall -q src tests
python -m pytest --strict-config --strict-markers -ra -W error
constructionsight audit-adapters
constructionsight audit-source-coverage data/source_registry.seed.json
python -m constructionsight.repository_certification --root . --require-clean-worktree
git diff --check
```

Warnings are errors. Test configuration and markers are strict. The certification command runs after tests and domain audits so test execution may not leave tracked or untracked residue.

## Defect and capability classification

The implementation-status matrix and full-repo audit inventory use two distinct ledgers:

1. **Resolved defects** record actual prior contradictions or unsafe behavior and the completed correction.
2. **Planned capabilities** record intentionally absent product scope and the conditions required before implementation.

Terms such as `partially fixed defect`, `known deferred defect`, or `acceptable failure` are not valid certification dispositions.

A newly discovered runtime, data-quality, documentation, persistence, provenance, compatibility, security, or CI defect immediately invalidates certification and blocks feature work until resolved.

## GitHub metadata requirements

Certification also requires:

- one active implementation phase recorded in the standing doctrine issue;
- accurate PR validation run and commit references;
- no open competing or superseded implementation PR;
- no unresolved review thread;
- an exact-head successful matrix; and
- verification that the merged tree is identical to the certified PR head tree.

GitHub metadata is reconciled through the GitHub API because it is not part of the tracked repository tree.

## Certification result

A certification result is valid only for the exact Git tree that passed all gates. A later commit requires a new complete run. Passing certification does not promote source maturity, establish recurring live coverage, make geometry survey-grade, authorize outreach, or imply that planned capabilities exist.
