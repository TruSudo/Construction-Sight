"""AST architecture and capability-acquisition certification."""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

from constructionsight.governance_certification_core import (
    _NETWORK_IMPORTS,
    _PERSISTENCE_IMPORTS,
    _SUBPROCESS_IMPORTS,
    GovernanceFinding,
    GovernanceMetrics,
    _compile_patterns,
    _external_matches,
    _finding,
    _imports,
    _module_name,
    _mutation_lines,
    _strongly_connected_components,
)


def _audit_architecture(
    root: Path,
    tracked: tuple[Path, ...],
    contract: Mapping[str, Any],
    network_contract: Mapping[str, Any],
    findings: list[GovernanceFinding],
) -> tuple[
    dict[str, str],
    dict[str, set[str]],
    dict[str, tuple[int, ...]],
    GovernanceMetrics,
]:
    path = "governance/architecture_contract.toml"
    raw_layers = contract.get("layers")
    if not isinstance(raw_layers, list) or not raw_layers:
        findings.append(_finding("ARCH-CONTRACT-001", path, "at least one layer is required"))
        return {}, {}, {}, GovernanceMetrics()

    layer_rules: list[
        tuple[
            str,
            tuple[re.Pattern[str], ...],
            bool,
            set[str],
            set[str],
            dict[str, bool],
        ]
    ] = []
    layer_names: set[str] = set()
    default_count = 0
    required_layer_fields = {
        "name",
        "responsibility",
        "path_patterns",
        "default",
        "allowed_internal_layers",
        "forbidden_internal_layers",
        "network",
        "persistence",
        "filesystem_write",
        "subprocess",
        "operator",
        "authority_bearing",
    }
    for raw in raw_layers:
        if not isinstance(raw, dict):
            findings.append(_finding("ARCH-CONTRACT-002", path, "each layer must be a table"))
            continue
        unknown = set(raw) - required_layer_fields
        missing = required_layer_fields - set(raw)
        if unknown or missing:
            findings.append(
                _finding(
                    "ARCH-CONTRACT-003",
                    path,
                    "layer fields disagree with schema; "
                    f"missing={sorted(missing)}, unknown={sorted(unknown)}",
                )
            )
            continue
        name = raw["name"]
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", name):
            findings.append(_finding("ARCH-CONTRACT-004", path, "layer name is invalid"))
            continue
        if name in layer_names:
            findings.append(_finding("ARCH-CONTRACT-005", path, f"duplicate layer {name}"))
            continue
        layer_names.add(name)
        patterns = _compile_patterns(
            raw["path_patterns"],
            path=path,
            field=f"{name}.path_patterns",
            findings=findings,
        )
        default = raw["default"] is True
        default_count += int(default)
        allowed = (
            set(raw["allowed_internal_layers"])
            if isinstance(raw["allowed_internal_layers"], list)
            else set()
        )
        forbidden = (
            set(raw["forbidden_internal_layers"])
            if isinstance(raw["forbidden_internal_layers"], list)
            else set()
        )
        permissions = {
            key: raw[key] is True
            for key in (
                "network",
                "persistence",
                "filesystem_write",
                "subprocess",
                "operator",
                "authority_bearing",
            )
        }
        layer_rules.append((name, patterns, default, allowed, forbidden, permissions))
    if default_count != 1:
        findings.append(
            _finding("ARCH-CONTRACT-006", path, "exactly one default layer is required")
        )

    module_paths = tuple(
        candidate
        for candidate in tracked
        if candidate.as_posix().startswith("src/constructionsight/") and candidate.suffix == ".py"
    )
    modules = {_module_name(candidate): candidate for candidate in module_paths}
    known = set(modules)
    layer_by_module: dict[str, str] = {}
    permissions_by_layer = {name: permissions for name, _, _, _, _, permissions in layer_rules}
    rule_by_layer = {
        name: (allowed, forbidden) for name, _, _, allowed, forbidden, _ in layer_rules
    }

    exception_pairs: set[tuple[str, str]] = set()
    raw_exceptions = contract.get("exceptions", [])
    if not isinstance(raw_exceptions, list):
        findings.append(
            _finding("ARCH-EXCEPTION-001", path, "exceptions must be an array of tables")
        )
        raw_exceptions = []
    exception_fields = {
        "source_module",
        "target_module",
        "reason",
        "risk",
        "compensating_control",
        "owner",
        "issued_on",
        "expires_on",
        "test",
        "adr",
    }
    for exception in raw_exceptions:
        if not isinstance(exception, dict):
            findings.append(
                _finding("ARCH-EXCEPTION-002", path, "each architecture exception must be a table")
            )
            continue
        missing = exception_fields - set(exception)
        unknown = set(exception) - exception_fields
        if missing or unknown:
            findings.append(
                _finding(
                    "ARCH-EXCEPTION-003",
                    path,
                    "exception fields disagree with schema; "
                    f"missing={sorted(missing)}, unknown={sorted(unknown)}",
                )
            )
            continue
        source_module = str(exception["source_module"])
        target_module = str(exception["target_module"])
        if "*" in source_module or "*" in target_module:
            findings.append(
                _finding(
                    "ARCH-EXCEPTION-004",
                    path,
                    "wildcard architecture exceptions are prohibited",
                )
            )
            continue
        if source_module not in known or target_module not in known:
            findings.append(
                _finding(
                    "ARCH-EXCEPTION-005",
                    path,
                    f"exception references unknown module edge: {source_module} -> {target_module}",
                )
            )
            continue
        try:
            issued_on = date.fromisoformat(str(exception["issued_on"]))
            expires_on = date.fromisoformat(str(exception["expires_on"]))
        except ValueError:
            findings.append(
                _finding("ARCH-EXCEPTION-006", path, "exception dates must be ISO dates")
            )
            continue
        if issued_on > expires_on or expires_on < date.today():
            findings.append(
                _finding(
                    "ARCH-EXCEPTION-007",
                    path,
                    "architecture exception is expired or invalid: "
                    f"{source_module} -> {target_module}",
                )
            )
        for artifact_field in ("test", "adr"):
            artifact = root / str(exception[artifact_field])
            if not artifact.is_file():
                findings.append(
                    _finding(
                        "ARCH-EXCEPTION-008",
                        path,
                        f"exception references missing {artifact_field}: "
                        f"{exception[artifact_field]}",
                    )
                )
        for text_field in ("reason", "risk", "compensating_control", "owner"):
            if not str(exception[text_field]).strip():
                findings.append(
                    _finding(
                        "ARCH-EXCEPTION-009",
                        path,
                        f"exception {text_field} must be nonempty",
                    )
                )
        exception_pairs.add((source_module, target_module))

    for module, module_path in sorted(modules.items()):
        display = module_path.as_posix()
        explicit = [
            name
            for name, patterns, default, _, _, _ in layer_rules
            if not default and any(pattern.fullmatch(display) for pattern in patterns)
        ]
        defaults = [name for name, _, default, _, _, _ in layer_rules if default]
        if len(explicit) > 1:
            findings.append(
                _finding(
                    "ARCH-CLASS-002",
                    module_path,
                    f"module matches multiple layers: {explicit}",
                )
            )
            continue
        if explicit:
            layer_by_module[module] = explicit[0]
        elif len(defaults) == 1:
            layer_by_module[module] = defaults[0]
        else:
            findings.append(_finding("ARCH-CLASS-001", module_path, "module is unclassified"))

    graph: dict[str, set[str]] = {module: set() for module in modules}
    mutation_map: dict[str, tuple[int, ...]] = {}
    network_modules = {
        value.get("module")
        for value in network_contract.get("policies", [])
        if isinstance(value, dict) and isinstance(value.get("module"), str)
    }
    for module, module_path in sorted(modules.items()):
        try:
            tree = ast.parse(
                (root / module_path).read_text(encoding="utf-8"),
                filename=module_path.as_posix(),
            )
        except (OSError, UnicodeError, SyntaxError):
            continue
        internal, external = _imports(tree, module, known)
        graph[module].update(target for target in internal if target != module)
        mutation_map[module] = _mutation_lines(tree)
        source_layer = layer_by_module.get(module)
        if source_layer is None:
            continue
        allowed, forbidden = rule_by_layer[source_layer]
        for target in sorted(internal):
            target_layer = layer_by_module.get(target)
            if target_layer is None or target_layer == source_layer:
                continue
            prohibited = target_layer in forbidden or target_layer not in allowed
            if prohibited and (module, target) not in exception_pairs:
                findings.append(
                    _finding(
                        "ARCH-IMPORT-001",
                        module_path,
                        f"{source_layer} cannot depend on {target_layer}: {module} -> {target}",
                    )
                )
        permissions = permissions_by_layer[source_layer]
        if _external_matches(external, _NETWORK_IMPORTS):
            if not permissions["network"]:
                findings.append(
                    _finding(
                        "ARCH-CAP-001",
                        module_path,
                        f"layer {source_layer} cannot acquire network capability",
                    )
                )
            if module not in network_modules:
                findings.append(
                    _finding(
                        "NET-BOUNDARY-001",
                        module_path,
                        "network-client import lacks an approved network policy",
                    )
                )
        if _external_matches(external, _PERSISTENCE_IMPORTS) and not permissions["persistence"]:
            findings.append(
                _finding(
                    "ARCH-CAP-002",
                    module_path,
                    f"layer {source_layer} cannot acquire persistence capability",
                )
            )
        if _external_matches(external, _SUBPROCESS_IMPORTS) and not permissions["subprocess"]:
            findings.append(
                _finding(
                    "ARCH-CAP-003",
                    module_path,
                    f"layer {source_layer} cannot acquire subprocess capability",
                )
            )
        if (
            mutation_map[module]
            and not permissions["filesystem_write"]
            and not permissions["persistence"]
        ):
            findings.append(
                _finding(
                    "ARCH-CAP-004",
                    module_path,
                    f"layer {source_layer} cannot perform detected mutation calls "
                    f"at lines {mutation_map[module]}",
                    mutation_map[module][0],
                )
            )

    components = _strongly_connected_components(graph)
    cycles = tuple(component for component in components if len(component) > 1)
    if contract.get("prohibit_module_cycles") is not True:
        findings.append(_finding("ARCH-CONTRACT-007", path, "prohibit_module_cycles must be true"))
    else:
        for component in cycles:
            findings.append(
                _finding(
                    "ARCH-CYCLE-001",
                    "src/constructionsight",
                    "prohibited internal import cycle: " + " -> ".join(component),
                )
            )

    edge_count = sum(len(targets) for targets in graph.values())
    metrics = GovernanceMetrics(
        architecture_nodes=len(modules),
        architecture_edges=edge_count,
        architecture_cycles=len(cycles),
    )
    return layer_by_module, graph, mutation_map, metrics
