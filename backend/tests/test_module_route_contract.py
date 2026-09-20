from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_app_registers_current_user_modules_router():
    from app import app

    included = [route for route in app.routes if route.__class__.__name__ == "_IncludedRouter"]
    module_includes = [
        route for route in included
        if getattr(route, "include_context", None)
        and route.include_context.prefix == "/api/me"
        and "modules" in route.include_context.tags
    ]

    assert len(module_includes) == 1
    assert any(
        child.path == "/modules" and child.methods == {"GET"}
        for child in module_includes[0].original_router.routes
    )


def test_app_registers_admin_tenant_module_management_router():
    from app import app

    included = [route for route in app.routes if route.__class__.__name__ == "_IncludedRouter"]
    admin_module_includes = [
        route for route in included
        if getattr(route, "include_context", None)
        and route.include_context.prefix == "/auth/admin"
        and "admin-modules" in route.include_context.tags
    ]

    assert len(admin_module_includes) == 1
    child_paths = {(child.path, tuple(sorted(child.methods))) for child in admin_module_includes[0].original_router.routes}
    assert ("/tenants/{tenant_id}/modules", ("GET",)) in child_paths
    assert ("/tenants/{tenant_id}/modules/{module_code}", ("PATCH",)) in child_paths


def test_supply_chain_protected_routes_have_module_guard_contracts():
    supplier_text = (REPO_ROOT / "supply_chain" / "supplier_router.py").read_text()
    batch_text = (REPO_ROOT / "supply_chain" / "batch_router.py").read_text()

    supplier_management_routes = [
        '@router.get("/suppliers", dependencies=[Depends(require_module("supplier_management"))])',
        '@router.get("/suppliers/eligible", dependencies=[Depends(require_module("supplier_management"))])',
        '@router.get("/certificate-risk-alerts", dependencies=[Depends(require_module("supplier_management"))])',
        '@router.post("/suppliers", dependencies=[Depends(require_module("supplier_management"))])',
        '@router.get("/suppliers/{sid}/certificates/{cid}/view", dependencies=[Depends(require_module("supplier_management"))])',
    ]
    for route in supplier_management_routes:
        assert route in supplier_text

    # Supplier portal token routes are intentionally public/external and must not
    # acquire get_current_user/module dependencies in the sandbox rollout.
    assert '@router.get("/supplier-portal/{token}")' in supplier_text
    assert '@router.post("/supplier-portal/{token}/upload")' in supplier_text

    traceability_routes = [
        '@router.get("/batches", dependencies=[Depends(require_module("traceability"))])',
        '@router.post("/batches", dependencies=[Depends(require_module("traceability"))])',
        '@router.get("/batches/{bid}", dependencies=[Depends(require_module("traceability"))])',
        '@router.post("/batches/{bid}/export-pdf", dependencies=[Depends(require_module("traceability"))])',
    ]
    for route in traceability_routes:
        assert route in batch_text

    assert '@router.get("/batches/{bid}/qr", dependencies=[Depends(require_module("public_trace"))])' in batch_text
    # Public/tokenized reads remain anonymous/token-compatible and fail closed in
    # their own handlers. A normal module guard would require get_current_user and
    # break window.open/token public evidence links.
    assert '@router.get("/batches/{bid}/steps/{step_id}/photo/view")' in batch_text
    # Public QR trace read endpoint remains anonymous and fail-closed via sealed
    # opaque trace-id/public_trace_enabled DB checks, not current-user modules.
    assert '@router.get("/batches/trace/{trace_id}")' in batch_text
