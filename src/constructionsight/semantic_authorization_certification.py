"""Resolved, path-sensitive certification for high-impact authorization."""

from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Final

from constructionsight.governance_certification_core import (
    GovernanceFinding,
    _finding,
    _module_name,
)

_HIGH_IMPACT_CONFIRMATIONS: Final = frozenset(
    {
        "apply_changes",
        "authorize_persistence",
        "check_http",
        "execute_live",
        "execute_write",
    }
)
_COMBINED_AUTHORIZER: Final = (
    "constructionsight.local_operator_authorization.authorize_local_operator_operation"
)
_DECISION_BUILDER: Final = "constructionsight.authorization_decision.build_authorization_decision"
_AUTHORIZATION_PREFLIGHT: Final = (
    "constructionsight.authorization_decision.validate_authorization_decision"
)
_OWNED_EFFECT_CONSUMER: Final = (
    "constructionsight.effect_consumption._execute_owned_effect"
)
_EFFECT_TARGETS: Final = frozenset(
    {
        "constructionsight.adapters.ceqanet_listing_executor.execute_ceqanet_listing_plan",
        "constructionsight.ceqanet_csv_live_service.execute_ceqanet_csv_live_request",
        "constructionsight.ceqanet_detail_http.execute_ceqanet_detail_request",
        "constructionsight.ceqanet_persistence_execute.execute_ceqanet_write_plan",
        "constructionsight.ceqanet_recurring_run_service.execute_ceqanet_recurring_run",
        "constructionsight.http_transport.execute_bounded_http",
        "constructionsight.lead_operator_service.transition_persisted_lead_workflow",
        "constructionsight.parcel_source_acquisition_http.execute_arcgis_probe_plan",
        "constructionsight.parcel_source_probe_http.execute_arcgis_bounded_probe",
        "constructionsight.result_authority_service.apply_authoritative_result",
        "constructionsight.source_readiness_http.check_source_http_reachability",
        "constructionsight.source_registry_apply_service.apply_source_registry_update_plan",
        "constructionsight.storage.parcel_source_acquisition_bundle_store."
        "store_arcgis_bounded_proof_bundle_chain",
    }
)
_STORAGE_MUTATION_PREFIXES: Final = (
    "add_",
    "compare_and_swap_",
    "delete_",
    "insert_",
    "store_",
    "update_",
    "upsert_",
)

_DYNAMIC_EFFECT_PARAMETERS: Final = frozenset(
    {
        "consumption_store",
        "executor",
        "http_checker",
        "ledger",
        "persister",
        "reservation_store",
        "used_authorization_ids",
        "verifier",
    }
)
_FORBIDDEN_AUTHORIZED_SERVICE_PARAMETERS: Final = frozenset(
    {
        *_DYNAMIC_EFFECT_PARAMETERS,
        "clock",
        "now",
    }
)
_AUTHORIZED_SERVICE_PREFIXES: Final = (
    "apply_authorized_",
    "build_authorized_",
    "execute_authorized_",
    "persist_authorized_",
)
_DYNAMIC_EFFECT: Final = "<dynamic-effect-boundary>"
_INDIRECT_CALL: Final = "<unresolved-indirect-call>"

_FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


class _AuthorizationPhase(Enum):
    NONE = "none"
    DECISION = "decision"
    AUTHORIZED = "authorized"
    CONSUMED = "consumed"


@dataclass
class _State:
    phase: _AuthorizationPhase
    authorized_once: bool = False
    booleans: dict[str, frozenset[bool]] = field(default_factory=dict)
    aliases: dict[str, frozenset[str]] = field(default_factory=dict)

    def clone(self) -> _State:
        return _State(
            phase=self.phase,
            authorized_once=self.authorized_once,
            booleans=dict(self.booleans),
            aliases=dict(self.aliases),
        )


@dataclass(frozen=True)
class _FunctionInfo:
    target: str
    module: str
    path: Path
    node: _FunctionNode
    parameters: tuple[str, ...]
    defaults: Mapping[str, ast.expr]
    class_name: str | None = None


@dataclass
class _ModuleInfo:
    name: str
    path: Path
    tree: ast.Module
    imports: dict[str, str] = field(default_factory=dict)
    module_aliases: dict[str, str] = field(default_factory=dict)
    functions: dict[str, str] = field(default_factory=dict)
    classes: dict[str, str] = field(default_factory=dict)
    global_aliases: dict[str, frozenset[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class _Program:
    modules: Mapping[str, _ModuleInfo]
    functions: Mapping[str, _FunctionInfo]
    classes: frozenset[str]

    def normalize_target(self, target: str) -> str:
        """Resolve simple package re-exports without trusting their local name."""

        candidate = target
        visited: set[str] = set()
        while candidate not in visited:
            visited.add(candidate)
            if candidate in self.functions:
                return candidate
            matched = False
            for module_name in sorted(self.modules, key=len, reverse=True):
                prefix = f"{module_name}."
                if not candidate.startswith(prefix):
                    continue
                local_name = candidate[len(prefix) :]
                module = self.modules[module_name]
                imported = module.imports.get(local_name)
                if imported is None:
                    return candidate
                candidate = imported
                matched = True
                break
            if not matched:
                return candidate
        return candidate


def _parameter_data(node: _FunctionNode) -> tuple[tuple[str, ...], dict[str, ast.expr]]:
    positional = (*node.args.posonlyargs, *node.args.args)
    parameters = [argument.arg for argument in positional]
    parameters.extend(argument.arg for argument in node.args.kwonlyargs)
    defaults: dict[str, ast.expr] = {}
    if node.args.defaults:
        for argument, value in zip(
            positional[-len(node.args.defaults) :],
            node.args.defaults,
            strict=True,
        ):
            defaults[argument.arg] = value
    for argument, kw_default in zip(
        node.args.kwonlyargs,
        node.args.kw_defaults,
        strict=True,
    ):
        if kw_default is not None:
            defaults[argument.arg] = kw_default
    return tuple(parameters), defaults


def _import_module(current: str, node: ast.ImportFrom) -> str:
    module = node.module or ""
    if not node.level:
        return module
    package = current.split(".")[:-1]
    trim = max(node.level - 1, 0)
    if trim > len(package):
        return ""
    base = package[: len(package) - trim]
    if module:
        base.extend(module.split("."))
    return ".".join(base)


def _collect_module_bindings(module: _ModuleInfo) -> None:
    for node in module.tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                module.module_aliases[local] = alias.name
        elif isinstance(node, ast.ImportFrom):
            imported_module = _import_module(module.name, node)
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                module.imports[local] = f"{imported_module}.{alias.name}"
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            target = f"{module.name}.{node.name}"
            module.functions[node.name] = target
        elif isinstance(node, ast.ClassDef):
            module.classes[node.name] = f"{module.name}.{node.name}"


def _module_callable_aliases(
    node: ast.expr,
    module: _ModuleInfo,
) -> frozenset[str]:
    if isinstance(node, ast.Name):
        if node.id in module.global_aliases:
            return module.global_aliases[node.id]
        if node.id in module.functions:
            return frozenset({module.functions[node.id]})
        if node.id in module.classes:
            return frozenset({module.classes[node.id]})
        if node.id in module.imports:
            return frozenset({module.imports[node.id]})
        if node.id in module.module_aliases:
            return frozenset({module.module_aliases[node.id]})
        return frozenset()
    if isinstance(node, ast.Attribute):
        return frozenset(
            f"{target}.{node.attr}" for target in _module_callable_aliases(node.value, module)
        )
    if isinstance(node, ast.BoolOp):
        return frozenset(
            target for value in node.values for target in _module_callable_aliases(value, module)
        )
    if isinstance(node, ast.Tuple | ast.List | ast.Set):
        resolved = {
            target for value in node.elts for target in _module_callable_aliases(value, module)
        }
        if resolved:
            resolved.add(_INDIRECT_CALL)
        return frozenset(resolved)
    if isinstance(node, ast.IfExp):
        return frozenset(
            {
                *_module_callable_aliases(node.body, module),
                *_module_callable_aliases(node.orelse, module),
            }
        )
    if isinstance(node, ast.Subscript):
        resolved = set(_module_callable_aliases(node.value, module))
        resolved.add(_INDIRECT_CALL)
        return frozenset(resolved)
    return frozenset()


def _collect_module_aliases(module: _ModuleInfo) -> None:
    changed = True
    while changed:
        changed = False
        for node in module.tree.body:
            target: ast.expr | None = None
            value: ast.expr | None = None
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                target = node.target
                value = node.value
            if not isinstance(target, ast.Name) or value is None:
                continue
            resolved = _module_callable_aliases(value, module)
            if resolved and module.global_aliases.get(target.id) != resolved:
                module.global_aliases[target.id] = resolved
                changed = True


def _build_program(
    root: Path,
    tracked_files: Sequence[Path],
    findings: list[GovernanceFinding],
) -> _Program:
    modules: dict[str, _ModuleInfo] = {}
    functions: dict[str, _FunctionInfo] = {}
    for relative in sorted((Path(path) for path in tracked_files), key=Path.as_posix):
        if not relative.as_posix().startswith("src/constructionsight/") or relative.suffix != ".py":
            continue
        try:
            tree = ast.parse(
                (root / relative).read_text(encoding="utf-8"),
                filename=str(relative),
            )
        except (OSError, UnicodeError, SyntaxError) as exc:
            findings.append(
                _finding(
                    "AUTH-AST-001",
                    relative,
                    f"semantic authorization AST could not be parsed: {exc}",
                )
            )
            continue
        module_name = _module_name(relative)
        modules[module_name] = _ModuleInfo(module_name, relative, tree)

    for module in modules.values():
        _collect_module_bindings(module)
    for module in modules.values():
        _collect_module_aliases(module)
    for module in modules.values():
        for node in module.tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                parameters, defaults = _parameter_data(node)
                target = f"{module.name}.{node.name}"
                functions[target] = _FunctionInfo(
                    target,
                    module.name,
                    module.path,
                    node,
                    parameters,
                    defaults,
                )
            elif isinstance(node, ast.ClassDef):
                for child in node.body:
                    if not isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                        continue
                    parameters, defaults = _parameter_data(child)
                    target = f"{module.name}.{node.name}.{child.name}"
                    functions[target] = _FunctionInfo(
                        target,
                        module.name,
                        module.path,
                        child,
                        parameters,
                        defaults,
                        node.name,
                    )
    return _Program(
        modules,
        functions,
        frozenset(target for module in modules.values() for target in module.classes.values()),
    )


class _AuthorizationGraphAudit:
    def __init__(
        self,
        program: _Program,
        layer_by_module: Mapping[str, str],
        findings: list[GovernanceFinding],
    ) -> None:
        self._program = program
        self._layer_by_module = layer_by_module
        self._findings = findings
        self._finding_keys: set[tuple[str, str, int | None, str]] = set()
        self._cache: dict[tuple[object, ...], tuple[tuple[_AuthorizationPhase, bool], ...]] = {}

    def run(self) -> None:
        for function in sorted(
            self._program.functions.values(),
            key=lambda item: item.target,
        ):
            leaf = function.target.rpartition(".")[2]
            if not leaf.startswith(_AUTHORIZED_SERVICE_PREFIXES):
                continue
            forbidden = sorted(
                set(function.parameters) & _FORBIDDEN_AUTHORIZED_SERVICE_PARAMETERS
            )
            if forbidden:
                self._record(
                    "AUTH-CONSUMPTION-002",
                    function,
                    function.node,
                    "authorized production service exposes caller-selected effect, "
                    "time, or consumption state: " + ", ".join(forbidden),
                )
        for function in sorted(
            self._program.functions.values(),
            key=lambda item: item.target,
        ):
            if self._layer_by_module.get(function.module) != "cli":
                continue
            confirmations = set(function.parameters) & _HIGH_IMPACT_CONFIRMATIONS
            initial = _State(
                phase=_AuthorizationPhase.NONE,
                booleans={parameter: frozenset({False, True}) for parameter in function.parameters},
                aliases={
                    parameter: frozenset({_DYNAMIC_EFFECT})
                    for parameter in function.parameters
                    if parameter in _DYNAMIC_EFFECT_PARAMETERS
                },
            )
            outcomes = self._analyze_function(function, initial, ())
            if confirmations and not any(state.authorized_once for state in outcomes):
                self._record(
                    "AUTH-BOOLEAN-002",
                    function,
                    function.node,
                    "high-impact CLI confirmation has no resolved path through "
                    "canonical authorization and preflight; "
                    f"parameters={sorted(confirmations)}",
                )

    def _record(
        self,
        code: str,
        function: _FunctionInfo,
        node: ast.AST,
        message: str,
    ) -> None:
        line = getattr(node, "lineno", None)
        key = (code, function.path.as_posix(), line, message)
        if key in self._finding_keys:
            return
        self._finding_keys.add(key)
        self._findings.append(_finding(code, function.path, message, line))

    def _cache_key(self, function: _FunctionInfo, state: _State) -> tuple[object, ...]:
        return (
            function.target,
            state.phase,
            state.authorized_once,
            tuple(sorted((name, tuple(values)) for name, values in state.booleans.items())),
            tuple(sorted((name, tuple(values)) for name, values in state.aliases.items())),
        )

    def _analyze_function(
        self,
        function: _FunctionInfo,
        initial: _State,
        stack: tuple[str, ...],
    ) -> list[_State]:
        if function.target in stack:
            return [initial]
        key = self._cache_key(function, initial)
        cached = self._cache.get(key)
        if cached is not None:
            return [
                _State(phase=phase, authorized_once=authorized_once)
                for phase, authorized_once in cached
            ]
        active, returned = self._analyze_block(
            function.node.body,
            [initial],
            function,
            (*stack, function.target),
        )
        outcomes = self._compact([*active, *returned])
        self._cache[key] = tuple((state.phase, state.authorized_once) for state in outcomes)
        return outcomes

    def _analyze_block(
        self,
        statements: Sequence[ast.stmt],
        states: list[_State],
        function: _FunctionInfo,
        stack: tuple[str, ...],
    ) -> tuple[list[_State], list[_State]]:
        active = self._compact(states)
        returned: list[_State] = []
        for statement in statements:
            if not active:
                break
            active, new_returns = self._analyze_statement(
                statement,
                active,
                function,
                stack,
            )
            returned.extend(new_returns)
        return self._compact(active), self._compact(returned)

    def _analyze_statement(
        self,
        node: ast.stmt,
        states: list[_State],
        function: _FunctionInfo,
        stack: tuple[str, ...],
    ) -> tuple[list[_State], list[_State]]:
        if isinstance(node, ast.Expr):
            return self._analyze_expr(node.value, states, function, stack), []
        if isinstance(node, ast.Assign | ast.AnnAssign):
            value = node.value
            if value is None:
                return states, []
            evaluated = self._analyze_expr(value, states, function, stack)
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            output: list[_State] = []
            for state in evaluated:
                updated = state.clone()
                aliases = self._resolve_callable(value, function, state)
                booleans = self._truth_values(value, state)
                for target in targets:
                    self._assign_target(updated, target, aliases, booleans)
                output.append(updated)
            return self._compact(output), []
        if isinstance(node, ast.AugAssign):
            evaluated = self._analyze_expr(node.value, states, function, stack)
            for state in evaluated:
                self._clear_target(state, node.target)
            return self._compact(evaluated), []
        if isinstance(node, ast.If):
            tested = self._analyze_expr(node.test, states, function, stack)
            body_input: list[_State] = []
            else_input: list[_State] = []
            for state in tested:
                truth = self._truth_values(node.test, state)
                if True in truth:
                    body_input.append(state.clone())
                if False in truth:
                    else_input.append(state.clone())
            body_active, body_returns = self._analyze_block(
                node.body,
                body_input,
                function,
                stack,
            )
            else_active, else_returns = self._analyze_block(
                node.orelse,
                else_input,
                function,
                stack,
            )
            return (
                self._compact([*body_active, *else_active]),
                self._compact([*body_returns, *else_returns]),
            )
        if isinstance(node, ast.With | ast.AsyncWith):
            active = states
            for item in node.items:
                active = self._analyze_expr(
                    item.context_expr,
                    active,
                    function,
                    stack,
                )
                if item.optional_vars is not None:
                    for state in active:
                        self._clear_target(state, item.optional_vars)
            return self._analyze_block(node.body, active, function, stack)
        if isinstance(node, ast.Try):
            body_active, body_returns = self._analyze_block(
                node.body,
                states,
                function,
                stack,
            )
            normal_active, normal_returns = self._analyze_block(
                node.orelse,
                body_active,
                function,
                stack,
            )
            handler_active: list[_State] = []
            handler_returns: list[_State] = []
            for handler in node.handlers:
                active, returned = self._analyze_block(
                    handler.body,
                    [state.clone() for state in states],
                    function,
                    stack,
                )
                handler_active.extend(active)
                handler_returns.extend(returned)
            active_before_final = self._compact([*normal_active, *handler_active])
            returns_before_final = self._compact([*body_returns, *normal_returns, *handler_returns])
            if not node.finalbody:
                return active_before_final, returns_before_final
            final_active, final_returns = self._analyze_block(
                node.finalbody,
                active_before_final,
                function,
                stack,
            )
            final_from_returns, replacement_returns = self._analyze_block(
                node.finalbody,
                returns_before_final,
                function,
                stack,
            )
            return (
                final_active,
                self._compact([*final_returns, *final_from_returns, *replacement_returns]),
            )
        if isinstance(node, ast.For | ast.AsyncFor):
            iterated = self._analyze_expr(node.iter, states, function, stack)
            body_input = [state.clone() for state in iterated]
            for state in body_input:
                self._clear_target(state, node.target)
            body_active, body_returns = self._analyze_block(
                node.body,
                body_input,
                function,
                stack,
            )
            loop_exits = self._compact([*iterated, *body_active])
            else_active, else_returns = self._analyze_block(
                node.orelse,
                loop_exits,
                function,
                stack,
            )
            return else_active, self._compact([*body_returns, *else_returns])
        if isinstance(node, ast.While):
            tested = self._analyze_expr(node.test, states, function, stack)
            while_body_input: list[_State] = []
            while_exits: list[_State] = []
            for state in tested:
                truth = self._truth_values(node.test, state)
                if True in truth:
                    while_body_input.append(state.clone())
                if False in truth:
                    while_exits.append(state.clone())
            body_active, body_returns = self._analyze_block(
                node.body,
                while_body_input,
                function,
                stack,
            )
            else_active, else_returns = self._analyze_block(
                node.orelse,
                self._compact([*while_exits, *body_active]),
                function,
                stack,
            )
            return else_active, self._compact([*body_returns, *else_returns])
        if isinstance(node, ast.Match):
            matched = self._analyze_expr(node.subject, states, function, stack)
            active = [state.clone() for state in matched]
            match_returns: list[_State] = []
            for case in node.cases:
                case_active, case_returns = self._analyze_block(
                    case.body,
                    [state.clone() for state in matched],
                    function,
                    stack,
                )
                active.extend(case_active)
                match_returns.extend(case_returns)
            return self._compact(active), self._compact(match_returns)
        if isinstance(node, ast.Return):
            evaluated = (
                self._analyze_expr(node.value, states, function, stack)
                if node.value is not None
                else states
            )
            return [], self._compact(evaluated)
        if isinstance(node, ast.Raise):
            active = states
            if node.exc is not None:
                active = self._analyze_expr(node.exc, active, function, stack)
            if node.cause is not None:
                self._analyze_expr(node.cause, active, function, stack)
            return [], []
        if isinstance(node, ast.Assert):
            active = self._analyze_expr(node.test, states, function, stack)
            if node.msg is not None:
                active = self._analyze_expr(node.msg, active, function, stack)
            return active, []
        if isinstance(node, ast.Import | ast.ImportFrom):
            return self._apply_local_import(node, states, function), []
        if isinstance(node, ast.Break | ast.Continue):
            return [], []
        return states, []

    def _analyze_expr(
        self,
        node: ast.expr,
        states: list[_State],
        function: _FunctionInfo,
        stack: tuple[str, ...],
    ) -> list[_State]:
        if isinstance(node, ast.Call):
            active = states
            if not isinstance(node.func, ast.Name):
                active = self._analyze_expr(node.func, active, function, stack)
            for argument in node.args:
                active = self._analyze_expr(argument, active, function, stack)
            for keyword in node.keywords:
                active = self._analyze_expr(keyword.value, active, function, stack)
            call_output: list[_State] = []
            for state in active:
                targets = self._resolve_callable(node.func, function, state)
                if not targets:
                    call_output.append(state)
                    continue
                for target in sorted(targets):
                    call_output.extend(self._invoke(target, node, state.clone(), function, stack))
            return self._compact(call_output)
        if isinstance(node, ast.IfExp):
            tested = self._analyze_expr(node.test, states, function, stack)
            if_output: list[_State] = []
            for state in tested:
                truth = self._truth_values(node.test, state)
                if True in truth:
                    if_output.extend(
                        self._analyze_expr(node.body, [state.clone()], function, stack)
                    )
                if False in truth:
                    if_output.extend(
                        self._analyze_expr(
                            node.orelse,
                            [state.clone()],
                            function,
                            stack,
                        )
                    )
            return self._compact(if_output)
        if isinstance(node, ast.BoolOp):
            active = states
            finished: list[_State] = []
            for index, value in enumerate(node.values):
                evaluated = self._analyze_expr(value, active, function, stack)
                if index == len(node.values) - 1:
                    finished.extend(evaluated)
                    break
                continuing: list[_State] = []
                for state in evaluated:
                    truth = self._truth_values(value, state)
                    continue_value = isinstance(node.op, ast.And)
                    if continue_value in truth:
                        continuing.append(state.clone())
                    if (not continue_value) in truth:
                        finished.append(state.clone())
                active = self._compact(continuing)
            return self._compact(finished)
        if isinstance(node, ast.ListComp | ast.SetComp | ast.GeneratorExp):
            active = states
            for generator in node.generators:
                active = self._analyze_expr(generator.iter, active, function, stack)
                for state in active:
                    self._clear_target(state, generator.target)
                for condition in generator.ifs:
                    active = self._analyze_expr(condition, active, function, stack)
            return self._analyze_expr(node.elt, active, function, stack)
        if isinstance(node, ast.DictComp):
            active = states
            for generator in node.generators:
                active = self._analyze_expr(generator.iter, active, function, stack)
                for state in active:
                    self._clear_target(state, generator.target)
                for condition in generator.ifs:
                    active = self._analyze_expr(condition, active, function, stack)
            active = self._analyze_expr(node.key, active, function, stack)
            return self._analyze_expr(node.value, active, function, stack)
        if isinstance(node, ast.NamedExpr):
            active = self._analyze_expr(node.value, states, function, stack)
            for state in active:
                self._assign_target(
                    state,
                    node.target,
                    self._resolve_callable(node.value, function, state),
                    self._truth_values(node.value, state),
                )
            return self._compact(active)
        active = states
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.expr):
                active = self._analyze_expr(child, active, function, stack)
        return self._compact(active)

    def _invoke(
        self,
        raw_target: str,
        call: ast.Call,
        state: _State,
        caller: _FunctionInfo,
        stack: tuple[str, ...],
    ) -> list[_State]:
        if raw_target == _INDIRECT_CALL:
            self._record(
                "AUTH-INDIRECT-001",
                caller,
                call,
                "high-impact call target is selected indirectly and cannot be "
                "proved to preserve the resolved authorization path",
            )
            return [state]
        target = self._program.normalize_target(raw_target)
        if target == _COMBINED_AUTHORIZER:
            state.phase = _AuthorizationPhase.AUTHORIZED
            return [state]
        if target == _DECISION_BUILDER:
            state.phase = _AuthorizationPhase.DECISION
            return [state]
        if target == _AUTHORIZATION_PREFLIGHT:
            if state.phase is not _AuthorizationPhase.DECISION:
                self._record(
                    "AUTH-PREFLIGHT-001",
                    caller,
                    call,
                    "canonical authorization preflight is not dominated by its "
                    "resolved decision builder",
                )
            else:
                state.phase = _AuthorizationPhase.AUTHORIZED
            return [state]
        if target == _OWNED_EFFECT_CONSUMER:
            if state.phase is not _AuthorizationPhase.AUTHORIZED:
                self._record(
                    "AUTH-CONSUMPTION-001",
                    caller,
                    call,
                    "ConstructionSight-owned durable effect consumption is not "
                    "dominated by completed canonical authorization and preflight",
                )
            else:
                state.phase = _AuthorizationPhase.CONSUMED
                state.authorized_once = True
            return [state]
        if target == _DYNAMIC_EFFECT or self._is_effect_target(target):
            detail = "dynamic injected effect boundary" if target == _DYNAMIC_EFFECT else target
            self._record(
                "AUTH-BYPASS-001",
                caller,
                call,
                "reachable effect bypasses the ConstructionSight-owned atomic "
                f"consumption runner: {detail}",
            )
            return [state]
        callee = self._program.functions.get(target)
        if callee is not None:
            callee_initial = self._bind_call(callee, call, state, caller)
            outcomes = self._analyze_function(callee, callee_initial, stack)
            output: list[_State] = []
            for outcome in outcomes:
                updated = state.clone()
                updated.phase = outcome.phase
                updated.authorized_once = outcome.authorized_once
                output.append(updated)
            return output
        leaf = target.rpartition(".")[2]
        if target.startswith("constructionsight.") and leaf.startswith(
            _AUTHORIZED_SERVICE_PREFIXES
        ):
            self._record(
                "AUTH-GRAPH-001",
                caller,
                call,
                "authorized-looking application call could not be resolved to a "
                f"tracked implementation: {target}",
            )
        return [state]

    def _is_effect_target(self, target: str) -> bool:
        if target in _EFFECT_TARGETS:
            return True
        callee = self._program.functions.get(target)
        if callee is None or not callee.module.startswith("constructionsight.storage."):
            return False
        leaf = target.rpartition(".")[2]
        return leaf.startswith(_STORAGE_MUTATION_PREFIXES)

    def _bind_call(
        self,
        callee: _FunctionInfo,
        call: ast.Call,
        caller_state: _State,
        caller: _FunctionInfo,
    ) -> _State:
        supplied: dict[str, ast.expr] = {}
        for name, argument in zip(callee.parameters, call.args, strict=False):
            supplied[name] = argument
        for keyword in call.keywords:
            if keyword.arg is not None:
                supplied[keyword.arg] = keyword.value
        callee_state = _State(
            phase=caller_state.phase,
            authorized_once=caller_state.authorized_once,
        )
        for parameter in callee.parameters:
            argument_value: ast.expr | None
            if parameter in supplied:
                argument_value = supplied[parameter]
                value_function = caller
                value_state = caller_state
            else:
                argument_value = callee.defaults.get(parameter)
                value_function = callee
                value_state = _State(
                    phase=caller_state.phase,
                    authorized_once=caller_state.authorized_once,
                )
            if argument_value is not None:
                callee_state.booleans[parameter] = self._truth_values(
                    argument_value,
                    value_state,
                )
                aliases = self._resolve_callable(
                    argument_value,
                    value_function,
                    value_state,
                )
                if aliases:
                    callee_state.aliases[parameter] = aliases
            else:
                callee_state.booleans[parameter] = frozenset({False, True})
            if parameter in _DYNAMIC_EFFECT_PARAMETERS:
                existing = callee_state.aliases.get(parameter, frozenset())
                callee_state.aliases[parameter] = frozenset({*existing, _DYNAMIC_EFFECT})
        return callee_state

    def _resolve_callable(
        self,
        node: ast.expr,
        function: _FunctionInfo,
        state: _State,
    ) -> frozenset[str]:
        module = self._program.modules[function.module]
        if isinstance(node, ast.Name):
            if node.id in state.aliases:
                return state.aliases[node.id]
            if node.id in module.global_aliases:
                return module.global_aliases[node.id]
            if node.id in module.functions:
                return frozenset({module.functions[node.id]})
            if node.id in module.classes:
                return frozenset({module.classes[node.id]})
            if node.id in module.imports:
                return frozenset({module.imports[node.id]})
            if node.id in module.module_aliases:
                return frozenset({module.module_aliases[node.id]})
            if node.id in _DYNAMIC_EFFECT_PARAMETERS:
                return frozenset({_DYNAMIC_EFFECT})
            return frozenset()
        if isinstance(node, ast.Attribute):
            base = self._resolve_callable(node.value, function, state)
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == "self"
                and function.class_name is not None
            ):
                return frozenset({f"{function.module}.{function.class_name}.{node.attr}"})
            return frozenset(
                f"{target}.{node.attr}"
                for target in base
                if target not in {_DYNAMIC_EFFECT, _INDIRECT_CALL}
            )
        if isinstance(node, ast.BoolOp):
            resolved = {
                target
                for value in node.values
                for target in self._resolve_callable(value, function, state)
            }
            return frozenset(resolved)
        if isinstance(node, ast.Tuple | ast.List | ast.Set):
            resolved = {
                target
                for value in node.elts
                for target in self._resolve_callable(value, function, state)
            }
            if resolved:
                resolved.add(_INDIRECT_CALL)
            return frozenset(resolved)
        if isinstance(node, ast.Dict):
            resolved = {
                target
                for value in node.values
                if value is not None
                for target in self._resolve_callable(value, function, state)
            }
            if resolved:
                resolved.add(_INDIRECT_CALL)
            return frozenset(resolved)
        if isinstance(node, ast.IfExp):
            return frozenset(
                {
                    *self._resolve_callable(node.body, function, state),
                    *self._resolve_callable(node.orelse, function, state),
                }
            )
        if isinstance(node, ast.Subscript):
            resolved = set(self._resolve_callable(node.value, function, state))
            resolved.add(_INDIRECT_CALL)
            return frozenset(resolved)
        if isinstance(node, ast.Call):
            return frozenset(
                target
                for target in self._resolve_callable(node.func, function, state)
                if self._program.normalize_target(target) in self._program.classes
            )
        if isinstance(node, ast.Lambda):
            return frozenset()
        return frozenset()

    def _truth_values(self, node: ast.expr, state: _State) -> frozenset[bool]:
        if isinstance(node, ast.Constant):
            return frozenset({bool(node.value)})
        if isinstance(node, ast.Name):
            return state.booleans.get(node.id, frozenset({False, True}))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return frozenset(not value for value in self._truth_values(node.operand, state))
        if isinstance(node, ast.BoolOp):
            possible = self._truth_values(node.values[0], state)
            for value in node.values[1:]:
                right = self._truth_values(value, state)
                if isinstance(node.op, ast.And):
                    possible = frozenset(left and item for left in possible for item in right)
                else:
                    possible = frozenset(left or item for left in possible for item in right)
            return possible
        if isinstance(node, ast.IfExp):
            return frozenset(
                {
                    *self._truth_values(node.body, state),
                    *self._truth_values(node.orelse, state),
                }
            )
        if isinstance(node, ast.NamedExpr):
            return self._truth_values(node.value, state)
        if (
            isinstance(node, ast.Compare)
            and len(node.ops) == 1
            and len(node.comparators) == 1
            and isinstance(node.left, ast.Name)
            and isinstance(node.comparators[0], ast.Constant)
            and isinstance(node.comparators[0].value, bool)
        ):
            expected = node.comparators[0].value
            values = state.booleans.get(node.left.id, frozenset({False, True}))
            if isinstance(node.ops[0], ast.Eq | ast.Is):
                return frozenset(value is expected for value in values)
            if isinstance(node.ops[0], ast.NotEq | ast.IsNot):
                return frozenset(value is not expected for value in values)
        return frozenset({False, True})

    def _assign_target(
        self,
        state: _State,
        target: ast.expr,
        aliases: frozenset[str],
        booleans: frozenset[bool],
    ) -> None:
        if isinstance(target, ast.Name):
            state.booleans[target.id] = booleans
            if aliases:
                state.aliases[target.id] = aliases
            else:
                state.aliases.pop(target.id, None)
            return
        if isinstance(target, ast.Tuple | ast.List):
            for element in target.elts:
                self._clear_target(state, element)

    def _clear_target(self, state: _State, target: ast.expr) -> None:
        if isinstance(target, ast.Name):
            state.booleans[target.id] = frozenset({False, True})
            state.aliases.pop(target.id, None)
        elif isinstance(target, ast.Tuple | ast.List):
            for element in target.elts:
                self._clear_target(state, element)

    def _apply_local_import(
        self,
        node: ast.Import | ast.ImportFrom,
        states: list[_State],
        function: _FunctionInfo,
    ) -> list[_State]:
        bindings: dict[str, str] = {}
        if isinstance(node, ast.Import):
            for alias in node.names:
                bindings[alias.asname or alias.name.split(".")[0]] = alias.name
        else:
            imported_module = _import_module(function.module, node)
            for alias in node.names:
                if alias.name != "*":
                    bindings[alias.asname or alias.name] = f"{imported_module}.{alias.name}"
        output: list[_State] = []
        for state in states:
            updated = state.clone()
            for name, target in bindings.items():
                updated.aliases[name] = frozenset({target})
            output.append(updated)
        return self._compact(output)

    def _compact(self, states: list[_State]) -> list[_State]:
        grouped: dict[tuple[_AuthorizationPhase, bool], list[_State]] = {}
        for state in states:
            grouped.setdefault((state.phase, state.authorized_once), []).append(state)
        compacted: list[_State] = []
        for (phase, authorized_once), group in grouped.items():
            boolean_names = {name for state in group for name in state.booleans}
            alias_names = {name for state in group for name in state.aliases}
            booleans = {
                name: frozenset(
                    value
                    for state in group
                    for value in state.booleans.get(name, frozenset({False, True}))
                )
                for name in boolean_names
            }
            aliases = {
                name: frozenset(
                    target for state in group for target in state.aliases.get(name, frozenset())
                )
                for name in alias_names
            }
            compacted.append(
                _State(
                    phase=phase,
                    authorized_once=authorized_once,
                    booleans=booleans,
                    aliases=aliases,
                )
            )
        return compacted


def audit_semantic_authorization(
    root: Path,
    tracked_files: Sequence[Path],
    layer_by_module: Mapping[str, str],
    findings: list[GovernanceFinding],
) -> None:
    """Prove canonical authorization ordering on every high-impact call path."""

    repository_root = root.resolve()
    program = _build_program(repository_root, tracked_files, findings)
    _AuthorizationGraphAudit(program, layer_by_module, findings).run()
