from constructionsight.adapters.audit import audit_adapter_contracts
from constructionsight.adapters.registry import AdapterRegistry, default_adapter_registry
from constructionsight.adapters.specs import default_adapter_family_specs
from constructionsight.adapters.stub import AccelaAcaAdapter
from constructionsight.models import PlatformFamily


def test_adapter_contract_audit_passes_for_defaults() -> None:
    result = audit_adapter_contracts(
        default_adapter_registry(),
        default_adapter_family_specs(),
    )

    assert result.passed is True
    assert result.missing_specs == ()
    assert result.missing_registrations == ()


def test_adapter_contract_audit_detects_missing_specs() -> None:
    registry = AdapterRegistry()
    registry.add(PlatformFamily.ACCELA_ACA, AccelaAcaAdapter)

    result = audit_adapter_contracts(registry, {})

    assert result.passed is False
    assert result.missing_specs == (PlatformFamily.ACCELA_ACA,)
    assert result.missing_registrations == ()


def test_adapter_contract_audit_detects_missing_registrations() -> None:
    specs = default_adapter_family_specs()
    registry = AdapterRegistry()

    result = audit_adapter_contracts(registry, specs)

    assert result.passed is False
    assert PlatformFamily.ACCELA_ACA in result.missing_registrations
    assert PlatformFamily.CEQANET in result.missing_registrations
