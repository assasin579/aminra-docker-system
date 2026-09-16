from __future__ import annotations

from collections.abc import Callable
from fastapi import params


def _first_dependency(router) -> Callable:
    dependencies = [dep for dep in router.dependencies if isinstance(dep, params.Depends)]
    assert dependencies
    dependency = dependencies[0].dependency
    assert callable(dependency)
    return dependency


def test_material_router_has_supplier_management_module_guard_dependency():
    from supply_chain.material_router import router

    dependency = _first_dependency(router)
    assert dependency.__name__ == "dependency"
    assert dependency.__closure__ is not None
    assert any(cell.cell_contents == "supplier_management" for cell in dependency.__closure__)


def test_process_router_has_process_digitization_module_guard_dependency():
    from supply_chain.process_router import router

    dependency = _first_dependency(router)
    assert dependency.__name__ == "dependency"
    assert dependency.__closure__ is not None
    assert any(cell.cell_contents == "process_digitization" for cell in dependency.__closure__)
