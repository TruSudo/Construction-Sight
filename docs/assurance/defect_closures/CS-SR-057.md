# CS-SR-057 Permanent Closure Evidence

Defect: `CS-SR-057 — foundational-domain-invariants`

## Historical root cause

Foundational site, permit, and planning models could admit physically impossible coordinates or measurements and contradictory lifecycle dates into durable projections.

## Resolution

Implementation commit: `f0086bebd54a8261311741eea66379c27e9edcf8`

Resolution tree: `cd853dd0da066466199d995a9ceda525846c3487`

Site coordinates are now bounded to valid latitude/longitude ranges and lot size is nonnegative. Permit lifecycle validation rejects issued/finaled dates that precede known earlier lifecycle dates. Planning-case validation likewise rejects hearing or approval dates that contradict known filing/hearing chronology while retaining legitimate unknown/partial states.

## Regression and retained evidence

`tests/test_permit_models.py`, `tests/test_planning_models.py`, and `tests/test_site_models.py` exercise the physical and chronology boundaries. Dashboard regressions were synchronized so contradictory permit chronology is rejected at the authoritative model boundary rather than merely displayed as a later limitation.

This closure preserves the historical finding and retires the corrected root cause.
