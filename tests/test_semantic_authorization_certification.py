from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from textwrap import dedent

from constructionsight.governance_certification_core import GovernanceFinding
from constructionsight.semantic_authorization_certification import (
    audit_semantic_authorization,
)

_CLI_PATH = "src/constructionsight/example_cli.py"
_CLI_MODULE = "constructionsight.example_cli"


def _module_name(relative: Path) -> str:
    parts = list(relative.relative_to("src").with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _audit_sources(
    tmp_path: Path,
    sources: Mapping[str, str],
    *,
    cli_modules: frozenset[str] = frozenset({_CLI_MODULE}),
) -> list[GovernanceFinding]:
    tracked: list[Path] = []
    layers: dict[str, str] = {}
    for relative_text, source in sources.items():
        relative = Path(relative_text)
        absolute = tmp_path / relative
        absolute.parent.mkdir(parents=True, exist_ok=True)
        absolute.write_text(dedent(source).lstrip(), encoding="utf-8")
        tracked.append(relative)
        module = _module_name(relative)
        layers[module] = "cli" if module in cli_modules else "application"
    findings: list[GovernanceFinding] = []
    audit_semantic_authorization(tmp_path, tracked, layers, findings)
    return findings


def _audit(tmp_path: Path, source: str) -> list[GovernanceFinding]:
    return _audit_sources(tmp_path, {_CLI_PATH: source})


def _codes(findings: list[GovernanceFinding]) -> set[str]:
    return {finding.code for finding in findings}


def test_boolean_only_high_impact_cli_is_rejected(tmp_path: Path) -> None:
    findings = _audit(
        tmp_path,
        """
        def execute(execute_live: bool) -> None:
            if execute_live:
                render_preview()
        """,
    )

    assert "AUTH-BOOLEAN-002" in _codes(findings)


def test_direct_resolved_effect_is_rejected_without_authorization(
    tmp_path: Path,
) -> None:
    findings = _audit(
        tmp_path,
        """
        from constructionsight.http_transport import execute_bounded_http

        def execute(execute_live: bool) -> None:
            execute_bounded_http()
        """,
    )

    assert "AUTH-BYPASS-001" in _codes(findings)
    assert "AUTH-BOOLEAN-002" in _codes(findings)


def test_import_and_local_aliases_resolve_to_authorization_and_effect(
    tmp_path: Path,
) -> None:
    findings = _audit(
        tmp_path,
        """
        import constructionsight.http_transport as transport
        from constructionsight.effect_consumption import _execute_owned_effect as consume
        from constructionsight.local_operator_authorization import (
            authorize_local_operator_operation as grant,
        )

        def execute(execute_live: bool) -> None:
            send = transport.execute_bounded_http
            grant()
            consume(effect=send)
        """,
    )

    assert findings == []


def test_module_level_effect_alias_is_resolved(tmp_path: Path) -> None:
    findings = _audit(
        tmp_path,
        """
        from constructionsight.http_transport import execute_bounded_http

        send = execute_bounded_http

        def execute(execute_live: bool) -> None:
            send()
        """,
    )

    assert "AUTH-BYPASS-001" in _codes(findings)


def test_spoofed_authorized_name_cannot_hide_an_effect(tmp_path: Path) -> None:
    findings = _audit(
        tmp_path,
        """
        from constructionsight.http_transport import execute_bounded_http

        def execute_authorized_spoof() -> None:
            execute_bounded_http()

        def execute(execute_live: bool) -> None:
            execute_authorized_spoof()
        """,
    )

    assert "AUTH-BYPASS-001" in _codes(findings)
    assert "AUTH-BOOLEAN-002" in _codes(findings)


def test_spoofed_authorized_method_cannot_hide_an_effect(tmp_path: Path) -> None:
    findings = _audit(
        tmp_path,
        """
        from constructionsight.http_transport import execute_bounded_http

        class Spoof:
            def execute_authorized(self) -> None:
                execute_bounded_http()

        def execute(execute_live: bool) -> None:
            service = Spoof()
            service.execute_authorized()
        """,
    )

    assert "AUTH-BYPASS-001" in _codes(findings)
    assert "AUTH-BOOLEAN-002" in _codes(findings)


def test_unresolved_authorized_looking_import_fails_closed(tmp_path: Path) -> None:
    findings = _audit(
        tmp_path,
        """
        from constructionsight.missing_service import execute_authorized_missing

        def execute(execute_live: bool) -> None:
            execute_authorized_missing()
        """,
    )

    assert "AUTH-GRAPH-001" in _codes(findings)
    assert "AUTH-BOOLEAN-002" in _codes(findings)


def test_indirect_effect_selection_is_rejected_even_after_authorization(
    tmp_path: Path,
) -> None:
    findings = _audit(
        tmp_path,
        """
        from constructionsight.http_transport import execute_bounded_http as send
        from constructionsight.local_operator_authorization import (
            authorize_local_operator_operation as grant,
        )

        def execute(execute_live: bool) -> None:
            callbacks = [send]
            grant()
            callbacks[0]()
        """,
    )

    assert "AUTH-INDIRECT-001" in _codes(findings)
    assert "AUTH-BYPASS-001" in _codes(findings)


def test_branch_bypass_is_rejected(tmp_path: Path) -> None:
    findings = _audit(
        tmp_path,
        """
        from constructionsight.http_transport import execute_bounded_http as send
        from constructionsight.local_operator_authorization import (
            authorize_local_operator_operation as grant,
        )

        def execute(execute_live: bool) -> None:
            if execute_live:
                grant()
            send()
        """,
    )

    assert "AUTH-BYPASS-001" in _codes(findings)


def test_effect_before_authorization_is_rejected(tmp_path: Path) -> None:
    findings = _audit(
        tmp_path,
        """
        from constructionsight.http_transport import execute_bounded_http as send
        from constructionsight.local_operator_authorization import (
            authorize_local_operator_operation as grant,
        )

        def execute(execute_live: bool) -> None:
            send()
            grant()
        """,
    )

    assert "AUTH-BYPASS-001" in _codes(findings)


def test_swallowed_authorization_failure_does_not_dominate_effect(
    tmp_path: Path,
) -> None:
    findings = _audit(
        tmp_path,
        """
        from constructionsight.http_transport import execute_bounded_http as send
        from constructionsight.local_operator_authorization import (
            authorize_local_operator_operation as grant,
        )

        def execute(execute_live: bool) -> None:
            try:
                grant()
            except RuntimeError:
                pass
            send()
        """,
    )

    assert "AUTH-BYPASS-001" in _codes(findings)


def test_validation_without_resolved_decision_builder_is_rejected(
    tmp_path: Path,
) -> None:
    findings = _audit(
        tmp_path,
        """
        from constructionsight.authorization_decision import validate_authorization_decision
        from constructionsight.effect_consumption import _execute_owned_effect as consume

        def execute(execute_live: bool) -> None:
            validate_authorization_decision()
            consume()
        """,
    )

    assert "AUTH-PREFLIGHT-001" in _codes(findings)
    assert "AUTH-CONSUMPTION-001" in _codes(findings)
    assert "AUTH-BOOLEAN-002" in _codes(findings)


def test_resolved_decision_preflight_and_effect_order_is_accepted(
    tmp_path: Path,
) -> None:
    findings = _audit(
        tmp_path,
        """
        from constructionsight.authorization_decision import (
            build_authorization_decision as build,
            validate_authorization_decision as validate,
        )
        from constructionsight.effect_consumption import _execute_owned_effect as consume
        from constructionsight.http_transport import execute_bounded_http as send

        def execute(execute_live: bool) -> None:
            build()
            validate()
            consume(effect=send)
        """,
    )

    assert findings == []


def test_interprocedural_authorization_path_is_accepted(tmp_path: Path) -> None:
    findings = _audit_sources(
        tmp_path,
        {
            _CLI_PATH: """
                from constructionsight.example_service import perform

                def execute(execute_live: bool) -> None:
                    perform()
            """,
            "src/constructionsight/example_service.py": """
                from constructionsight.effect_consumption import _execute_owned_effect
                from constructionsight.http_transport import execute_bounded_http
                from constructionsight.local_operator_authorization import (
                    authorize_local_operator_operation,
                )

                def perform() -> None:
                    authorize_local_operator_operation()
                    _execute_owned_effect(effect=execute_bounded_http)
            """,
        },
    )

    assert findings == []


def test_interprocedural_effect_before_authorization_is_rejected(
    tmp_path: Path,
) -> None:
    findings = _audit_sources(
        tmp_path,
        {
            _CLI_PATH: """
                from constructionsight.example_service import perform

                def execute(execute_live: bool) -> None:
                    perform()
            """,
            "src/constructionsight/example_service.py": """
                from constructionsight.http_transport import execute_bounded_http
                from constructionsight.local_operator_authorization import (
                    authorize_local_operator_operation,
                )

                def perform() -> None:
                    execute_bounded_http()
                    authorize_local_operator_operation()
            """,
        },
    )

    assert "AUTH-BYPASS-001" in _codes(findings)


def test_direct_effect_after_authorization_still_bypasses_atomic_consumption(
    tmp_path: Path,
) -> None:
    findings = _audit(
        tmp_path,
        """
        from constructionsight.http_transport import execute_bounded_http as send
        from constructionsight.local_operator_authorization import (
            authorize_local_operator_operation as grant,
        )

        def execute(execute_live: bool) -> None:
            grant()
            send()
        """,
    )

    assert "AUTH-BYPASS-001" in _codes(findings)
    assert "AUTH-BOOLEAN-002" in _codes(findings)


def test_owned_consumption_without_authorization_is_rejected(tmp_path: Path) -> None:
    findings = _audit(
        tmp_path,
        """
        from constructionsight.effect_consumption import _execute_owned_effect

        def execute(execute_live: bool) -> None:
            _execute_owned_effect()
        """,
    )

    assert "AUTH-CONSUMPTION-001" in _codes(findings)
    assert "AUTH-BOOLEAN-002" in _codes(findings)


def test_authorized_service_cannot_expose_caller_consumption_or_time_seams(
    tmp_path: Path,
) -> None:
    findings = _audit_sources(
        tmp_path,
        {
            _CLI_PATH: """
                def execute(execute_live: bool) -> None:
                    return None
            """,
            "src/constructionsight/example_service.py": """
                def execute_authorized_example(*, ledger) -> None:
                    return None
            """,
        },
    )

    assert "AUTH-CONSUMPTION-002" in _codes(findings)


def test_registry_apply_confirmation_is_high_impact(tmp_path: Path) -> None:
    findings = _audit(
        tmp_path,
        """
        def apply(apply_changes: bool) -> None:
            render_preview()
        """,
    )

    assert "AUTH-BOOLEAN-002" in _codes(findings)


def test_http_check_confirmation_is_high_impact(tmp_path: Path) -> None:
    findings = _audit(
        tmp_path,
        """
        def build(check_http: bool) -> None:
            render_preview()
        """,
    )

    assert "AUTH-BOOLEAN-002" in _codes(findings)


def test_non_cli_module_is_outside_operator_entry_rule(tmp_path: Path) -> None:
    relative = "src/constructionsight/transport.py"
    findings = _audit_sources(
        tmp_path,
        {
            relative: """
                from constructionsight.http_transport import execute_bounded_http

                def execute(execute_live: bool) -> None:
                    execute_bounded_http()
            """,
        },
        cli_modules=frozenset(),
    )

    assert findings == []
